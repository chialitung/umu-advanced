"""Course management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class CourseEndpoint:
    """Course, session, and content element endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def get(self, course_id: Any) -> Any:
        """GET /uapi/v1/course/{id}"""
        return self.client.get("/uapi/v1/course/{id}", path_params={"id": course_id})

    def get_certificate_info(self, **params: Any) -> Any:
        """GET /uapi/v1/course/certificate-info"""
        return self.client.get("/uapi/v1/course/certificate-info", params=params)

    def get_creator(self, **params: Any) -> Any:
        """GET /uapi/v1/course/creator"""
        return self.client.get("/uapi/v1/course/creator", params=params)

    def get_enroll_info(self, **params: Any) -> Any:
        """GET /uapi/v1/course/enroll-info"""
        return self.client.get("/uapi/v1/course/enroll-info", params=params)

    def get_certificate_templates(self, **params: Any) -> Any:
        """GET /uapi/v1/course/get-certificate-template-list"""
        return self.client.get("/uapi/v1/course/get-certificate-template-list", params=params)

    def get_mini_program_config(self, **params: Any) -> Any:
        """GET /uapi/v1/course/get-course-mini-program-config"""
        return self.client.get("/uapi/v1/course/get-course-mini-program-config", params=params)

    def get_custom_certificate(self, **params: Any) -> Any:
        """GET /uapi/v1/course/get-custom-certificate"""
        return self.client.get("/uapi/v1/course/get-custom-certificate", params=params)

    def get_timing_switch(self, **params: Any) -> Any:
        """GET /uapi/v1/course/get-timing-switch"""
        return self.client.get("/uapi/v1/course/get-timing-switch", params=params)

    def save_certificate(self, data: dict) -> Any:
        """POST /uapi/v1/course/save-certificate"""
        return self.client.post("/uapi/v1/course/save-certificate", json=data)

    def get_u_score(self, **params: Any) -> Any:
        """GET /uapi/v1/course/u-score"""
        return self.client.get("/uapi/v1/course/u-score", params=params)

    def get_element(self, element_id: Any) -> Any:
        """GET /uapi/v1/element/{id}"""
        return self.client.get("/uapi/v1/element/{id}", path_params={"id": element_id})

    def list_sessions_by_group(self, **params: Any) -> Any:
        """GET /ajax/session/getsessionlistbygroup"""
        return self.client.get("/ajax/session/getsessionlistbygroup", params=params)

    def get_session(self, **params: Any) -> Any:
        """GET /ajax/session/getsessionInfo"""
        return self.client.get("/ajax/session/getsessionInfo", params=params)

    def save_session(self, data: dict) -> Any:
        """POST /api/session/savesession"""
        return self.client.post("/api/session/savesession", json=data)

    def get_participate_status(self, **params: Any) -> Any:
        """GET /uapi/v1/session/participate-status"""
        return self.client.get("/uapi/v1/session/participate-status", params=params)

    # -- New endpoints from 学习课程.har --

    def get_element_siblings_nav(self, **params: Any) -> Any:
        """GET /napi/element/get-siblings-nav"""
        return self.client.get("/napi/element/get-siblings-nav", params=params)

    def get_student_chapter_session(self, **params: Any) -> Any:
        """GET /napi/v1/student/course/chapter-session"""
        return self.client.get("/napi/v1/student/course/chapter-session", params=params)

    def get_student_element_list(self, **params: Any) -> Any:
        """GET /napi/v1/student/course/element-list"""
        return self.client.get("/napi/v1/student/course/element-list", params=params)

    def get_student_session_resources(self, data: dict) -> Any:
        """POST /napi/v1/student/course/session-list-resource"""
        return self.client.post("/napi/v1/student/course/session-list-resource", json=data)

    def list_group_certificates(self, **params: Any) -> Any:
        """GET /api/group/certificatelist"""
        return self.client.get("/api/group/certificatelist", params=params)

    def get_exam_session_status(self, **params: Any) -> Any:
        """GET /uapi/v1/exam/session-status"""
        return self.client.get("/uapi/v1/exam/session-status", params=params)

    def list_comments(self, **params: Any) -> Any:
        """GET /uapi/v2/comment/list"""
        return self.client.get("/uapi/v2/comment/list", params=params)

    def get_comment_banner(self, **params: Any) -> Any:
        """GET /uapi/v2/comment/banner-info"""
        return self.client.get("/uapi/v2/comment/banner-info", params=params)

    # -- New endpoints from 创建课程.har & 上传文档或视频.har --

    def save_group(self, data: dict) -> Any:
        """POST /ajax/e_saveGroup"""
        return self.client.post("/ajax/e_saveGroup", json=data)

    def get_default_template(self, **params: Any) -> Any:
        """GET /ajax/getDefaultTemplateByType"""
        return self.client.get("/ajax/getDefaultTemplateByType", params=params)

    def get_document_drive(self) -> Any:
        """GET /documentDrive"""
        return self.client.get("/documentDrive")

    def add_multimedia_fulltext(self, data: dict) -> Any:
        """POST /ajax/multimedia/fulltextadd"""
        return self.client.post("/ajax/multimedia/fulltextadd", json=data)
