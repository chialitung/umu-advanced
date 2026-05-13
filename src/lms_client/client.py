"""Main HTTP client for the LMS API."""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urljoin

import requests

from .auth import AuthBase, SessionAuth
from .exceptions import (
    LMSAPIError,
    LMSAuthError,
    LMSNotFoundError,
    LMSRateLimitError,
    LMSValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_BATCH_CONCURRENCY = 5


class LMSClient:
    """HTTP client for UMU LMS API."""

    def __init__(
        self,
        base_url: str = "https://www.umu.cn",
        auth: AuthBase | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = auth or SessionAuth()
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    def _build_url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _apply_auth(self, kwargs: dict) -> dict:
        """Inject authentication into request kwargs."""
        if isinstance(self.auth, SessionAuth):
            # Session auth uses the session object directly
            return kwargs
        return self.auth.apply(kwargs)

    def _handle_response(self, response: requests.Response) -> Any:
        """Check response status and raise appropriate exceptions."""
        status = response.status_code
        if status == 200:
            try:
                return response.json()
            except ValueError:
                return response.text

        body = None
        try:
            body = response.json()
        except ValueError:
            body = response.text

        msg = f"HTTP {status}"
        if isinstance(body, dict) and "msg" in body:
            msg = f"{msg}: {body['msg']}"
        elif isinstance(body, str) and body:
            msg = f"{msg}: {body[:200]}"

        if status in (401, 403):
            raise LMSAuthError(msg, status, body)
        if status == 404:
            raise LMSNotFoundError(msg, status, body)
        if status == 429:
            raise LMSRateLimitError(msg, status, body)
        if status in (400, 422):
            raise LMSValidationError(msg, status, body)

        raise LMSAPIError(msg, status, body)

    def request(
        self,
        method: str,
        path: str,
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an authenticated HTTP request with retries."""
        path_params = path_params or {}
        resolved_path = path
        for key, value in path_params.items():
            resolved_path = resolved_path.replace(f"{{{key}}}", str(value))

        url = self._build_url(resolved_path)
        kwargs.setdefault("timeout", self.timeout)
        kwargs = self._apply_auth(kwargs)

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("%s %s (attempt %d)", method, url, attempt)
                if isinstance(self.auth, SessionAuth):
                    response = self.auth.session.request(method, url, **kwargs)
                else:
                    response = self._session.request(method, url, **kwargs)
                return self._handle_response(response)
            except (LMSAuthError, LMSRateLimitError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning("Retrying after %ds due to %s", wait, exc)
                    time.sleep(wait)
                    if isinstance(exc, LMSAuthError):
                        if self.auth.refresh():
                            kwargs = self._apply_auth(kwargs)
                else:
                    raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning("Request failed, retrying in %ds: %s", wait, exc)
                    time.sleep(wait)
                else:
                    raise LMSAPIError(f"Request failed after {self.max_retries} attempts: {exc}") from exc

        raise LMSAPIError(f"Request failed: {last_exc}")

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def list_all(
        self,
        path: str,
        page_param: str = "page",
        size_param: str = "size",
        data_key: str | None = "data",
        **kwargs: Any,
    ) -> list[dict]:
        """Auto-traverse paginated list endpoints.

        For UMU APIs, extracts ``total_page_num`` from ``page_info`` and
        iterates exactly that many pages, avoiding data loss from the old
        ``len(items) < size`` heuristic. Falls back to the heuristic for
        non-UMU endpoints that do not expose ``total_page_num``.
        """
        results: list[dict] = []
        params = dict(kwargs.get("params", {}))
        params[page_param] = params.get(page_param, 1)
        params[size_param] = params.get(size_param, 20)
        kwargs["params"] = params

        total_page_num: int | None = None

        while True:
            resp = self.get(path, **kwargs)
            items: list[dict] = []
            page_info: dict | None = None

            if isinstance(resp, dict):
                container = resp
                if data_key:
                    container = resp.get(data_key, {})
                # UMU format: {"data": {"list": [...], "page_info": {...}}}
                if isinstance(container, dict):
                    raw_items = container.get("list")
                    if isinstance(raw_items, list):
                        items = raw_items
                    page_info = container.get("page_info")
                elif isinstance(container, list):
                    items = container
            elif isinstance(resp, list):
                items = resp

            if not isinstance(items, list):
                break

            results.extend(items)

            # Detect total_page_num from UMU page_info on first response
            if total_page_num is None and isinstance(page_info, dict):
                total_page_num = int(page_info.get("total_page_num", 0)) or None

            if total_page_num is not None:
                current_page = (
                    int(page_info.get("current_page", params[page_param]))
                    if isinstance(page_info, dict)
                    else params[page_param]
                )
                if current_page >= total_page_num:
                    break
            else:
                # Fallback for non-UMU APIs
                if len(items) < params[size_param]:
                    break

            params[page_param] += 1

        return results

    def batch_get(
        self,
        ids: list[Any],
        path_template: str,
        id_key: str = "id",
        concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    ) -> list[Any]:
        """Fetch multiple resources concurrently."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[Any] = []

        def fetch(single_id: Any) -> Any:
            try:
                return self.get(path_template, path_params={id_key: single_id})
            except LMSAPIError as exc:
                logger.warning("Failed to fetch %s=%s: %s", id_key, single_id, exc)
                return None

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(fetch, i): i for i in ids}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

        return results

    def batch_create(
        self,
        items: list[dict],
        path: str,
        concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    ) -> list[Any]:
        """Create multiple resources concurrently."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[Any] = []

        def create(item: dict) -> Any:
            try:
                return self.post(path, json=item)
            except LMSAPIError as exc:
                logger.warning("Failed to create item: %s", exc)
                return None

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(create, item): item for item in items}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

        return results

    def close(self) -> None:
        self._session.close()
        self.auth.close()

    def __enter__(self) -> "LMSClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
