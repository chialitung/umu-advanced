"""LMS API endpoint modules."""

from .base import EndpointBase
from .courses import CourseEndpoint
from .exams import ExamEndpoint
from .organizations import OrganizationEndpoint
from .reports import ReportEndpoint
from .resources import ResourceEndpoint
from .users import UserEndpoint

__all__ = [
    "EndpointBase",
    "UserEndpoint",
    "OrganizationEndpoint",
    "CourseEndpoint",
    "ExamEndpoint",
    "ReportEndpoint",
    "ResourceEndpoint",
]
