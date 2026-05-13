"""Report and analytics endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class ReportEndpoint:
    """Data report and analytics endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def get_dashboard(self, **params: Any) -> Any:
        """GET /ajax/enterprise/getreportdashboard"""
        return self.client.get("/ajax/enterprise/getreportdashboard", params=params)

    def list_report_groups(
        self,
        *,
        page: int = 1,
        size: int = 20,
        only_total_num: bool = False,
        **extra: Any,
    ) -> dict:
        """GET /ajax/enterprise/getReportGroupList

        List course groups with pagination and optional total-only mode.

        Args:
            page: Page number (1-based).
            size: Items per page.
            only_total_num: When True, returns only total count metadata.
            **extra: Additional query parameters forwarded to the API.

        Returns:
            API response envelope containing:
                - status (bool): Request success flag.
                - data (dict): Nested data with "list" and "page_info".
                - page_info (dict): Pagination metadata including list_total_num,
                  total_page_num, current_page, and size.

        Example response (only_total_num=False):
            {
                "status": True,
                "data": {
                    "list": [{"id": "7308856", "title": "...", ...}],
                    "page_info": {
                        "list_total_num": 25794,
                        "total_page_num": 1290,
                        "current_page": 1,
                        "size": 20,
                    },
                },
            }
        """
        params: dict[str, Any] = {"page": page, "size": size, **extra}
        if only_total_num:
            params["only_total_num"] = 1
        return self.client.get("/ajax/enterprise/getReportGroupList", params=params)

    def get_report_group_count(self, **extra: Any) -> int:
        """Return the total number of report groups.

        Uses the ``only_total_num=1`` shortcut to avoid fetching the full list.

        Args:
            **extra: Additional query parameters forwarded to the API.

        Returns:
            Total count of report groups, or 0 if the count cannot be determined.
        """
        result = self.list_report_groups(page=1, size=1, only_total_num=True, **extra)
        page_info = result.get("data", {}).get("page_info", {})
        return int(page_info.get("list_total_num", 0))

    def get_group_operation_logs(self, **params: Any) -> Any:
        """GET /uapi/v1/group/get-operation-log-list"""
        return self.client.get("/uapi/v1/group/get-operation-log-list", params=params)

    # -- New endpoints from 学习课程.har --

    def generate_report(self, data: dict) -> Any:
        """POST /uapi/v1/des/report"""
        return self.client.post("/uapi/v1/des/report", json=data)
