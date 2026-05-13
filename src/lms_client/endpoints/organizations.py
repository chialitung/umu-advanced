"""Organization / enterprise management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class OrganizationEndpoint:
    """Enterprise and organization management endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def get_info(self) -> Any:
        """GET /uapi/v1/enterprise/info"""
        return self.client.get("/uapi/v1/enterprise/info")

    def list_groups(self, **params: Any) -> Any:
        """GET /ajax/enterprise/getGroupList"""
        return self.client.get("/ajax/enterprise/getGroupList", params=params)

    def list_report_groups(self, **params: Any) -> Any:
        """GET /ajax/enterprise/getReportGroupList"""
        return self.client.get("/ajax/enterprise/getReportGroupList", params=params)

    def get_dashboard(self, **params: Any) -> Any:
        """GET /ajax/enterprise/getreportdashboard"""
        return self.client.get("/ajax/enterprise/getreportdashboard", params=params)

    def list_departments(self, **params: Any) -> Any:
        """GET /uapi/v1/department/get-departments-by-managerid"""
        return self.client.get("/uapi/v1/department/get-departments-by-managerid", params=params)

    def list_categories(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise/get-category-list"""
        return self.client.get("/uapi/v1/enterprise/get-category-list", params=params)

    def get_customize_config(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise/get-customize-config"""
        return self.client.get("/uapi/v1/enterprise/get-customize-config", params=params)

    def list_enterprise_groups(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise/enterprise-group-list"""
        return self.client.get("/uapi/v1/enterprise/enterprise-group-list", params=params)

    # -- New endpoints from 学习课程.har --

    def get_student_certificate_info(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise-certificate/get-student-certificate-info"""
        return self.client.get("/uapi/v1/enterprise-certificate/get-student-certificate-info", params=params)

    # -- New endpoints from 部门_分组_讲师管理.har --

    def update_group(self, data: dict) -> Any:
        """POST /ajax/enterprise/updateGroup"""
        return self.client.post("/ajax/enterprise/updateGroup", json=data)

    def update_group_user(self, data: dict) -> Any:
        """POST /ajax/enterprise/updateGroupUser"""
        return self.client.post("/ajax/enterprise/updateGroupUser", json=data)

    def batch_add_user_to_group(self, data: dict) -> Any:
        """POST /api/enterprise/batchaddusertogroup"""
        return self.client.post("/api/enterprise/batchaddusertogroup", json=data)

    def search_user_batch(self, **params: Any) -> Any:
        """GET /api/enterprise/searchuserbatch"""
        return self.client.get("/api/enterprise/searchuserbatch", params=params)

    def list_departments_by_level(self, **params: Any) -> Any:
        """GET /uapi/v1/department/get-all-bylevel"""
        return self.client.get("/uapi/v1/department/get-all-bylevel", params=params)

    def list_child_departments(self, **params: Any) -> Any:
        """GET /uapi/v1/department/get-childdepartments-byid"""
        return self.client.get("/uapi/v1/department/get-childdepartments-byid", params=params)

    def list_department_members(self, **params: Any) -> Any:
        """GET /uapi/v1/department/member-list"""
        return self.client.get("/uapi/v1/department/member-list", params=params)

    def list_users_not_in_department(self, **params: Any) -> Any:
        """GET /uapi/v1/department/users-not-in-department"""
        return self.client.get("/uapi/v1/department/users-not-in-department", params=params)

    def list_enterprise_group_users(self, **params: Any) -> Any:
        """GET /uapi/v1/enterprise/enterprise-group-user-list"""
        return self.client.get("/uapi/v1/enterprise/enterprise-group-user-list", params=params)

    def list_enterprise_lecturing_records(self, **params: Any) -> Any:
        """GET /uapi/v1/teacher-manage/enterprise-lecturing-record-list"""
        return self.client.get("/uapi/v1/teacher-manage/enterprise-lecturing-record-list", params=params)
