"""User management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class UserEndpoint:
    """User and student management endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def list_enterprise_users(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise/user-list"""
        return self.client.get("/uapi/v1/enterprise/user-list", params=params)

    def list_students(self, **params: Any) -> Any:
        """GET /api/studentManage/getstudentlist"""
        return self.client.get("/api/studentManage/getstudentlist", params=params)

    def get_student_tasks(self, **params: Any) -> Any:
        """GET /api/studentManage/getstudenttasklist"""
        return self.client.get("/api/studentManage/getstudenttasklist", params=params)

    def get_account_plan(self) -> Any:
        """GET /uapi/v1/user/account-plan"""
        return self.client.get("/uapi/v1/user/account-plan")

    def get_private_policy_check(self) -> Any:
        """GET /uapi/v1/user/private-policy-check-info"""
        return self.client.get("/uapi/v1/user/private-policy-check-info")

    def list_sign_users(self, **params: Any) -> Any:
        """GET /uapi/v1/sign/user-list"""
        return self.client.get("/uapi/v1/sign/user-list", params=params)

    def list_lecturing_teachers(self, **params: Any) -> Any:
        """GET /uapi/v1/teacher-manage/lecturing-teacher-list-by-course"""
        return self.client.get("/uapi/v1/teacher-manage/lecturing-teacher-list-by-course", params=params)

    # -- New endpoints from 学习课程.har --

    def is_teacher(self) -> Any:
        """GET /uapi/v1/user/is-teacher"""
        return self.client.get("/uapi/v1/user/is-teacher")

    def get_poll_result_summary(self, **params: Any) -> Any:
        """GET /uapi/v1/poll/user-result-summary"""
        return self.client.get("/uapi/v1/poll/user-result-summary", params=params)

    def get_poll_user_result(self, **params: Any) -> Any:
        """GET /uapi/v1/poll/get-user-result"""
        return self.client.get("/uapi/v1/poll/get-user-result", params=params)

    # -- New endpoints from 部门_分组_讲师管理.har --

    def get_login_accounts(self) -> Any:
        """GET /uapi/v1/user/get-login-accounts"""
        return self.client.get("/uapi/v1/user/get-login-accounts")

    def is_admin(self, email: str | None = None) -> bool:
        """Check whether the user is an administrator.

        When *email* is omitted, the method attempts to derive it from
        ``/uapi/v1/user/account-plan`` (``enterprise_main_account``).

        Parameters
        ----------
        email:
            User email to query.  If ``None``, auto-detect from account-plan.

        Returns
        -------
        bool
            ``True`` when the user's ``role_type`` equals ``"4"``.
        """
        if email is None:
            plan = self.get_account_plan()
            if isinstance(plan, dict):
                data = plan.get("data", {})
                email = data.get("enterprise_main_account") if isinstance(data, dict) else None
            if not email:
                raise ValueError(
                    "email is required when enterprise_main_account cannot be auto-detected"
                )

        result = self.client.get(
            "/ajax/enterprise/getUserList",
            params={"keywords": email, "page": 1, "size": 20},
        )
        if not isinstance(result, dict):
            return False

        data = result.get("data", {})
        users = data.get("list", []) if isinstance(data, dict) else []
        if not users:
            return False

        role_type = users[0].get("role_type")
        return role_type == "4"

    def get_user_list(
        self,
        *,
        page: int = 1,
        size: int = 500,
        keywords: str | None = None,
        **extra: Any,
    ) -> dict:
        """GET /ajax/enterprise/getUserList

        List enterprise users with pagination.

        Args:
            page: Page number (1-based).
            size: Items per page.
            keywords: Optional search keyword (email, name, etc.).
            **extra: Additional query parameters forwarded to the API.

        Returns:
            API response envelope containing:
                - status (bool): Request success flag.
                - data (dict): Nested data with "list" and "page_info".
        """
        params: dict[str, Any] = {"page": page, "size": size, **extra}
        if keywords:
            params["keywords"] = keywords
        return self.client.get("/ajax/enterprise/getUserList", params=params)

    def get_user_list_count(self, **extra: Any) -> int:
        """Return the total number of enterprise users."""
        result = self.get_user_list(page=1, size=1, **extra)
        page_info = result.get("data", {}).get("page_info", {})
        return int(page_info.get("list_total_num", 0))

    def list_teacher_manage_dashboard(self, **params: Any) -> Any:
        """GET /uapi/v1/dashboard/teacher-manage-list"""
        return self.client.get("/uapi/v1/dashboard/teacher-manage-list", params=params)

    def list_teacher_tags(self, **params: Any) -> Any:
        """GET /uapi/v1/teacher-manage/tag-list"""
        return self.client.get("/uapi/v1/teacher-manage/tag-list", params=params)
