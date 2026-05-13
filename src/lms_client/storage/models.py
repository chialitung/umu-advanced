"""SQLAlchemy ORM models for LMS data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import declarative_base

from ..timeutil import now_beijing

Base: Any = declarative_base()


class SyncMixin:
    """Mixin adding sync metadata columns."""

    id = Column(Integer, primary_key=True, autoincrement=True)
    synced_at = Column(DateTime, default=now_beijing, onupdate=now_beijing)
    sync_version = Column(Integer, default=1)


class User(Base, SyncMixin):
    """User / employee record."""

    __tablename__ = "users"

    user_id = Column(String(64), index=True)
    name = Column(String(255))
    email = Column(String(255))
    mobile = Column(String(64))
    department = Column(String(255))
    role = Column(String(64))
    status = Column(Integer, default=1)
    raw_data = Column(JSON)

    # UMU Advanced extended fields
    umu_id = Column(String(64), index=True, unique=True)
    number = Column(String(64))
    user_name = Column(String(255))
    account_joining_time = Column(DateTime)
    departments = Column(Text)
    role_type = Column(String(16))
    is_admin = Column(Boolean, default=False)


class Organization(Base, SyncMixin):
    """Enterprise / organization record."""

    __tablename__ = "organizations"

    org_id = Column(String(64), index=True)
    name = Column(String(255))
    type = Column(String(64))
    status = Column(Integer, default=1)
    raw_data = Column(JSON)


class Course(Base, SyncMixin):
    """Course / group record."""

    __tablename__ = "courses"

    course_id = Column(String(64), index=True, unique=True)
    group_id = Column(String(64), index=True)
    name = Column(String(512))
    creator_id = Column(String(64))
    status = Column(Integer, default=1)
    raw_data = Column(JSON)

    # UMU Advanced extended fields
    title = Column(String(512))
    creat_time = Column(DateTime)
    source = Column(String(255))
    desc = Column(Text)
    update_time = Column(DateTime)
    head_img_old = Column(String(1024))
    head_img_new = Column(String(1024))
    course_cover = Column(LargeBinary)
    lesson_type = Column(String(64))
    group_time = Column(DateTime)
    umu_id = Column(String(64))
    share_url = Column(String(1024))
    access_code = Column(String(64))
    categoryArr = Column(JSON)
    multimedia_id = Column(String(32), nullable=True)
    last_fetch_time = Column(DateTime)


class Session(Base, SyncMixin):
    """Course session / meeting record."""

    __tablename__ = "sessions"

    session_id = Column(String(64), index=True)
    course_id = Column(String(64), index=True)
    name = Column(String(512))
    status = Column(Integer, default=1)
    raw_data = Column(JSON)

    # Governance extension fields
    session_type = Column(String(16))
    is_require = Column(Integer)
    questions = Column(JSON)
    type_name = Column(String(64))
    chapter_id = Column(String(64))


class CourseGroupTime(Base, SyncMixin):
    """Course schedule / duration record for governance rule 5."""

    __tablename__ = "course_group_times"

    group_id = Column(String(64), index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)


class GovernanceResult(Base, SyncMixin):
    """Per-course governance audit result."""

    __tablename__ = "governance_results"

    run_id = Column(String(64), index=True)
    course_id = Column(String(64), index=True)
    group_id = Column(String(64), index=True)
    course_name = Column(String(512))
    creator_email = Column(String(255))
    creator_name = Column(String(255))
    umu_link = Column(String(1024))
    overall_compliant = Column(Boolean, default=True)
    overall_level = Column(String(16))
    rule_results = Column(JSON)
    issues = Column(JSON)
    created_at = Column(DateTime, default=now_beijing)


class GovernanceRun(Base, SyncMixin):
    """Governance run batch record."""

    __tablename__ = "governance_runs"

    run_id = Column(String(64), unique=True, index=True)
    started_at = Column(DateTime, default=now_beijing)
    completed_at = Column(DateTime)
    total_courses = Column(Integer, default=0)
    processed_courses = Column(Integer, default=0)
    status = Column(String(16), default="running")
    error_message = Column(Text)
    start_date = Column(String(10))
    end_date = Column(String(10))


class StudentTask(Base, SyncMixin):
    """Student assignment / task record."""

    __tablename__ = "student_tasks"

    task_id = Column(String(64), index=True)
    user_id = Column(String(64), index=True)
    course_id = Column(String(64), index=True)
    title = Column(String(512))
    status = Column(String(64))
    score = Column(String(64))
    raw_data = Column(JSON)


class GovernanceConfig(Base):
    """Governance rule configuration storage."""

    __tablename__ = "governance_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, index=True, nullable=False)
    config_value = Column(JSON)
    description = Column(String(255))
    updated_at = Column(DateTime, default=now_beijing, onupdate=now_beijing)
