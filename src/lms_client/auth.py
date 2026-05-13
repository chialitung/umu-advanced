"""Authentication modules for the LMS client."""

from __future__ import annotations

import base64
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger(__name__)


# UMU login page uses AES-256-CBC with a hard-coded key/IV derived from
# the "muumuu" brand name.  Key and IV are parsed as UTF-8 bytes.
_UMU_AES_KEY = "muumuumuumuumuumuumuumumumuumuum".encode("utf-8")
_UMU_AES_IV = "mumumuumumumumum".encode("utf-8")


def encrypt_password(password: str) -> str:
    """Encrypt a password using UMU's frontend AES-256-CBC scheme.

    The encryption logic was reverse-engineered from
    ``pc_common_umu_pc.f320012e.js`` which calls
    ``CryptoJS.AES.encrypt(password, key, {iv, mode: CBC, padding: Pkcs7})``.

    Parameters
    ----------
    password:
        Plain-text password.

    Returns
    -------
    str
        Base64-encoded ciphertext.

    Raises
    ------
    ImportError
        If ``cryptography`` is not installed.
    """
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "UMU password encryption requires 'cryptography'. "
            "Install it with: pip install cryptography"
        ) from exc

    cipher = Cipher(
        algorithms.AES(_UMU_AES_KEY),
        modes.CBC(_UMU_AES_IV),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()
    padded = _pkcs7_pad(password.encode("utf-8"), block_size=16)
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("ascii")


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    """Apply PKCS#7 padding."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def decrypt_password(encrypted_b64: str) -> str:
    """Decrypt a UMU AES-256-CBC encrypted password (for testing/debugging).

    Parameters
    ----------
    encrypted_b64:
        Base64-encoded ciphertext.

    Returns
    -------
    str
        Plain-text password.
    """
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "UMU password decryption requires 'cryptography'. "
            "Install it with: pip install cryptography"
        ) from exc

    ciphertext = base64.b64decode(encrypted_b64)
    cipher = Cipher(
        algorithms.AES(_UMU_AES_KEY),
        modes.CBC(_UMU_AES_IV),
        backend=default_backend(),
    )
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    return _pkcs7_unpad(padded).decode("utf-8")


def _pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS#7 padding."""
    pad_len = data[-1]
    if pad_len > len(data) or pad_len == 0:
        return data
    return data[:-pad_len]


class AuthBase(ABC):
    """Abstract base class for authentication strategies."""

    @abstractmethod
    def apply(self, request_kwargs: dict) -> dict:
        """Modify request kwargs to include authentication."""

    @abstractmethod
    def refresh(self) -> bool:
        """Attempt to refresh authentication. Return True if successful."""

    def __enter__(self) -> "AuthBase":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Clean up resources. Override if needed."""


class TokenAuth(AuthBase):
    """Bearer / API token authentication with optional auto-refresh."""

    def __init__(
        self,
        token: str | None = None,
        refresh_token: str | None = None,
        refresh_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        login_url: str | None = None,
    ):
        self.token = token
        self.refresh_token = refresh_token
        self.refresh_url = refresh_url
        self.username = username
        self.password = password
        self.login_url = login_url

    def apply(self, request_kwargs: dict) -> dict:
        headers = dict(request_kwargs.get("headers", {}))
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request_kwargs["headers"] = headers
        return request_kwargs

    def refresh(self) -> bool:
        if self.refresh_token and self.refresh_url:
            try:
                resp = requests.post(
                    self.refresh_url,
                    json={"refresh_token": self.refresh_token},
                    timeout=30,
                )
                data = resp.json()
                self.token = data.get("token") or data.get("access_token")
                self.refresh_token = data.get("refresh_token") or self.refresh_token
                logger.info("Token refreshed successfully")
                return True
            except Exception as exc:
                logger.warning("Token refresh failed: %s", exc)

        if self.username and self.password and self.login_url:
            try:
                resp = requests.post(
                    self.login_url,
                    json={"username": self.username, "password": self.password},
                    timeout=30,
                )
                data = resp.json()
                self.token = data.get("token") or data.get("access_token")
                self.refresh_token = data.get("refresh_token") or self.refresh_token
                logger.info("Re-logged in successfully")
                return True
            except Exception as exc:
                logger.warning("Re-login failed: %s", exc)

        return False


class SessionAuth(AuthBase):
    """Cookie-based session authentication using requests.Session."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def apply(self, request_kwargs: dict) -> dict:
        # Session handles cookies automatically; just ensure session is used
        return request_kwargs

    def refresh(self) -> bool:
        # Session refresh would require re-login logic specific to the platform
        logger.warning("Session refresh not implemented")
        return False

    def close(self) -> None:
        self.session.close()


class UMUSessionAuth(SessionAuth):
    """UMU-specific session auth that performs cookie-based login with AES password encryption.

    Reverse-engineered from the UMU login page (``pc_common_umu_pc.f320012e.js``).
    Passwords are encrypted with AES-256-CBC using a hard-coded key before being
    sent to ``/passport/ajax/account/login``.
    """

    LOGIN_PATH = "/passport/ajax/account/login"
    TOKEN_PATTERN = re.compile(r'"token":"([^"]+)"')

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        base_url: str = "https://www.umu.cn",
        session: requests.Session | None = None,
    ):
        super().__init__(session)
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None

    def login(self) -> dict:
        """Authenticate and establish a session cookie.

        Returns
        -------
        dict
            Parsed JSON response from the login endpoint.

        Raises
        ------
        LMSAuthError
            If credentials are missing or the server rejects the login.
        """
        if not self.username or not self.password:
            raise RuntimeError("username and password are required for login")

        # 1. Fetch the login page to obtain the anti-CSRF / session token
        login_page_url = f"{self.base_url}/auth/login"
        resp = self.session.get(login_page_url, timeout=30)
        resp.raise_for_status()

        # Extract token from inline JS: window.pageData = {"token":"..."}
        match = self.TOKEN_PATTERN.search(resp.text)
        self._token = match.group(1) if match else None

        # 2. Encrypt password using UMU's AES-256-CBC scheme
        encrypted_pass = encrypt_password(self.password)

        # 3. Submit login request
        login_url = f"{self.base_url}{self.LOGIN_PATH}"
        payload = {
            "username": self.username,
            "passwd": encrypted_pass,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        login_resp = self.session.post(
            login_url,
            data=payload,
            headers=headers,
            timeout=30,
        )
        login_resp.raise_for_status()
        data = login_resp.json()

        if not data.get("status") and data.get("error"):
            raise RuntimeError(f"Login failed: {data['error']}")

        logger.info("UMU login successful for %s", self.username)
        return data

    def refresh(self) -> bool:
        """Re-login using stored credentials."""
        try:
            self.login()
            return True
        except Exception as exc:
            logger.warning("UMU session refresh failed: %s", exc)
            return False


class AuthFactory:
    """Factory to create the appropriate auth instance from HAR analysis."""

    @staticmethod
    def create_from_har_analysis(auth_info: dict) -> AuthBase:
        """Create an AuthBase subclass based on HAR-detected auth type."""
        auth_type = auth_info.get("auth_type", "none")
        if isinstance(auth_type, list):
            auth_type = auth_type[0] if auth_type else "none"

        if auth_type in ("bearer", "token_response"):
            return TokenAuth(
                token=auth_info.get("token"),
                refresh_token=auth_info.get("refresh_token"),
                refresh_url=auth_info.get("refresh_url"),
                username=auth_info.get("username"),
                password=auth_info.get("password"),
                login_url=auth_info.get("login_url"),
            )

        if auth_type in ("cookie", "session"):
            return SessionAuth()

        if auth_type == "umu_session":
            return UMUSessionAuth(
                username=auth_info.get("username"),
                password=auth_info.get("password"),
                base_url=auth_info.get("base_url", "https://www.umu.cn"),
            )

        # Default to session auth (most common for web apps)
        logger.info("No explicit auth type detected; defaulting to SessionAuth")
        return SessionAuth()
