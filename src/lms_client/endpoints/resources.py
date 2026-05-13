"""Resource upload and management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class ResourceEndpoint:
    """File, document, and video resource management endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def get_info(self, **params: Any) -> Any:
        """GET /ajax/resource/getresourceinfo"""
        return self.client.get("/ajax/resource/getresourceinfo", params=params)

    def list_resources(self, **params: Any) -> Any:
        """GET /ajax/resource/getresourcelist"""
        return self.client.get("/ajax/resource/getresourcelist", params=params)

    def rename_resource(self, data: dict) -> Any:
        """POST /ajax/resource/renameresource"""
        return self.client.post("/ajax/resource/renameresource", json=data)

    def pre_upload(self, data: dict) -> Any:
        """POST /microapi/resourcemgt/preObject

        Initiates a file upload by requesting a pre-signed upload URL.
        """
        return self.client.post("/microapi/resourcemgt/preObject", json=data)

    def upload_callback(self, data: dict) -> Any:
        """POST /microapi/resourcemgt/resourceCallback

        Notifies the server that a file upload has completed.
        """
        return self.client.post("/microapi/resourcemgt/resourceCallback", json=data)

    def add_log(self, **params: Any) -> Any:
        """GET /uapi/v1/resource/add-log"""
        return self.client.get("/uapi/v1/resource/add-log", params=params)

    def upload_file_direct(self, path: str, file_data: bytes, content_type: str = "application/octet-stream") -> Any:
        """PUT direct upload to a resource path.

        Args:
            path: The full resource path (e.g. /resource/S2c/.../{id}.pptx)
            file_data: Raw file bytes
            content_type: MIME type of the file
        """
        return self.client.put(path, data=file_data, headers={"Content-Type": content_type})
