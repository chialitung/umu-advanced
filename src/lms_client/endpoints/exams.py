"""Exam / quiz endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import LMSClient


class ExamEndpoint:
    """Exam, quiz, and assignment endpoints."""

    def __init__(self, client: LMSClient):
        self.client = client

    def list_my_assignments(self, **params: Any) -> Any:
        """GET /api/task/myassignmentlist"""
        return self.client.get("/api/task/myassignmentlist", params=params)

    def get_enroll_approval_setting(self, **params: Any) -> Any:
        """GET /uapi/v1/enroll/get-approval-setting"""
        return self.client.get("/uapi/v1/enroll/get-approval-setting", params=params)

    def get_designated_approver(self, **params: Any) -> Any:
        """GET /uapi/v1/enroll/get-designated-approver"""
        return self.client.get("/uapi/v1/enroll/get-designated-approver", params=params)

    def get_notification_setting(self, **params: Any) -> Any:
        """GET /uapi/v1/enroll/get-notification-setting"""
        return self.client.get("/uapi/v1/enroll/get-notification-setting", params=params)

    # -- New endpoints from 学习课程.har --

    def start_exam(self, data: dict) -> Any:
        """POST /megrez/exam/v1/startExam"""
        return self.client.post("/megrez/exam/v1/startExam", json=data)

    def save_answer(self, data: dict) -> Any:
        """POST /megrez/exam/v1/saveAnswer"""
        return self.client.post("/megrez/exam/v1/saveAnswer", json=data)

    def submit_exam(self, data: dict) -> Any:
        """POST /megrez/exam/v1/submitExam"""
        return self.client.post("/megrez/exam/v1/submitExam", json=data)

    def retake_exam(self, data: dict) -> Any:
        """POST /api/exam/takeexamagain"""
        return self.client.post("/api/exam/takeexamagain", json=data)

    def save_poll_result(self, data: dict) -> Any:
        """POST /megrez/poll/v1/save-poll-result"""
        return self.client.post("/megrez/poll/v1/save-poll-result", json=data)

    def save_user_poll_result(self, data: dict) -> Any:
        """POST /megrez/poll/v1/user-save-poll-result"""
        return self.client.post("/megrez/poll/v1/user-save-poll-result", json=data)
