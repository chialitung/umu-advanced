"""Base endpoint class with generic CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class EndpointBase:
    """Base class for all API endpoint modules."""

    path_prefix: str = ""

    def __init__(self, client: LMSClient):
        self.client = client

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        full_path = f"{self.path_prefix.rstrip('/')}/{path.lstrip('/')}" if self.path_prefix else path
        return self.client.request(method, full_path, **kwargs)

    def list(self, **filters: Any) -> list[dict]:
        """List resources with optional filters."""
        return self.client.list_all(self.path_prefix, params=filters)

    def get(self, resource_id: Any, sub_path: str = "") -> dict:
        """Get a single resource by ID."""
        path = f"{sub_path}/{resource_id}" if sub_path else f"{self.path_prefix.rstrip('/')}/{resource_id}"
        result = self.client.get(path)
        return result if isinstance(result, dict) else {}

    def create(self, data: dict, sub_path: str = "") -> dict:
        """Create a new resource."""
        path = sub_path or self.path_prefix
        result = self.client.post(path, json=data)
        return result if isinstance(result, dict) else {}

    def update(self, resource_id: Any, data: dict, sub_path: str = "") -> dict:
        """Update an existing resource."""
        path = f"{sub_path}/{resource_id}" if sub_path else f"{self.path_prefix.rstrip('/')}/{resource_id}"
        result = self.client.post(path, json=data)
        return result if isinstance(result, dict) else {}

    def delete(self, resource_id: Any, sub_path: str = "") -> dict:
        """Delete a resource."""
        path = f"{sub_path}/{resource_id}" if sub_path else f"{self.path_prefix.rstrip('/')}/{resource_id}"
        result = self.client.delete(path)
        return result if isinstance(result, dict) else {}
