"""Governance service for training data compliance auditing."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from lms_client.auth import SessionAuth
from lms_client.client import LMSClient
from lms_client.storage.models import (
    Base,
    Course,
    CourseGroupTime,
    GovernanceConfig,
    GovernanceResult,
    GovernanceRun,
    Session as SessionModel,
    User,
)

from .sync_service import deserialize_session
from lms_client.timeutil import now_beijing

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DATABASE_URL = f"sqlite:///{os.path.join(_PROJECT_ROOT, 'lms.db')}"

# Rule 1 & 2: forbidden words and exception words
FORBIDDEN_WORDS = {
    "接待",
    "交流",
    "访谈",
    "座谈",
    "茶话会",
    "员工沟通",
    "福利宣讲",
    "工会活动",
    "wellbeing",
    "员工大会",
    "志愿者活动",
    "团建",
    "报名",
    "问卷",
    "抽奖",
    "投票",
    "会议",
    "宣讲",
    "早会",
    "面谈",
    "晤谈",
    "电话会议",
    "心理健康",
    "党建",
    "督导",
    "团结",
    "优秀代表",
    "表彰",
    "纪念",
    "庆典",
}

EXCEPTION_WORDS = {
    "培训",
    "学习",
    "研讨",
    "研究",
    "课程",
    "教育",
    "辅导",
    "指导",
    "论坛",
    "工作坊",
    "角色扮演",
    "模拟演练",
    "案例分析",
    "小组讨论",
    "讲座",
    "导师",
    "讲解",
    "解读",
    "政策解读",
    "政策",
    "小测",
    "测验",
    "考试",
    "考卷",
    "试卷",
}

VALID_CATEGORIES = {"通用力", "专业力", "领导力", "新兴力"}

# Rule 6: evaluation keywords
EVALUATION_KEYWORDS = {
    "满意度",
    "帮助",
    "收获",
    "评价",
    "得分",
    "评分",
    "打分",
    "建议",
    "改进",
    "推荐",
    "探讨",
    "话题",
    "学习",
    "知识",
    "简要说明",
    "意见或建议",
}

# Rule 4: meaningless placeholders
MEANINGLESS_PLACEHOLDERS = {"课程大纲：", "课程大纲:", "课程大纲", "暂无", "待定"}

# Rule 8: empty content marker
EMPTY_CONTENT_MARKER = "b96beb74eb4e5ea5419d74b956c5404c"


def _title_matched_forbidden_words(
    title: str | None, forbidden_words: set[str] | None = None
) -> list[str]:
    """Return forbidden words appearing in title, longest match first."""
    if not title:
        return []
    words = forbidden_words if forbidden_words is not None else FORBIDDEN_WORDS
    matches = [fw for fw in words if fw in title]
    return sorted(matches, key=lambda w: (-len(w), w))


def _title_hits_exception(title: str | None, exception_words: set[str] | None = None) -> bool:
    """Check if title contains any exception word."""
    if not title:
        return False
    words = exception_words if exception_words is not None else EXCEPTION_WORDS
    return any(ew in title for ew in words)


# Default configuration values (mirrors hard-coded constants)
DEFAULT_CONFIGS: dict[str, Any] = {
    "forbidden_words": list(FORBIDDEN_WORDS),
    "exception_words": list(EXCEPTION_WORDS),
    "fallback_forbidden_words": [],
    "valid_categories": list(VALID_CATEGORIES),
    "evaluation_keywords": list(EVALUATION_KEYWORDS),
    "meaningless_placeholders": list(MEANINGLESS_PLACEHOLDERS),
    "empty_content_marker": EMPTY_CONTENT_MARKER,
    "excluded_umu_id": "13264912",
    "excluded_lesson_type": "999",
    "max_duration_hours": 30,
    "excluded_course_ids": [],
}


class GovernanceConfigService:
    """Manages governance rule configurations persisted in the database."""

    def __init__(self, database_url: str = DEFAULT_DATABASE_URL):
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Read a single config value by key."""
        session = self.SessionLocal()
        try:
            record = session.query(GovernanceConfig).filter_by(config_key=key).first()
            if record and record.config_value is not None:
                return record.config_value
            return DEFAULT_CONFIGS.get(key, default) if default is not None else DEFAULT_CONFIGS.get(key)
        finally:
            session.close()

    def get_all_configs(self) -> dict[str, Any]:
        """Return all stored configs merged with defaults."""
        session = self.SessionLocal()
        try:
            records = session.query(GovernanceConfig).all()
            stored = {r.config_key: r.config_value for r in records if r.config_value is not None}
            result = dict(DEFAULT_CONFIGS)
            result.update(stored)
            return result
        finally:
            session.close()

    def set_config(self, key: str, value: Any, description: str | None = None) -> None:
        """Write or update a single config value."""
        session = self.SessionLocal()
        try:
            record = session.query(GovernanceConfig).filter_by(config_key=key).first()
            if record:
                record.config_value = value
                if description is not None:
                    record.description = description
            else:
                session.add(
                    GovernanceConfig(
                        config_key=key,
                        config_value=value,
                        description=description or "",
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def init_defaults(self) -> None:
        """Initialize default configs in the database if not present."""
        session = self.SessionLocal()
        try:
            for key, value in DEFAULT_CONFIGS.items():
                existing = session.query(GovernanceConfig).filter_by(config_key=key).first()
                if not existing:
                    session.add(
                        GovernanceConfig(
                            config_key=key,
                            config_value=value,
                            description="",
                        )
                    )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def reset_to_defaults(self) -> None:
        """Reset all configs to default values."""
        session = self.SessionLocal()
        try:
            # Delete existing records
            session.query(GovernanceConfig).delete()
            # Re-insert defaults
            for key, value in DEFAULT_CONFIGS.items():
                session.add(
                    GovernanceConfig(
                        config_key=key,
                        config_value=value,
                        description="",
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_rule_config(self, rule_name: str) -> dict[str, Any]:
        """Get config dict for a specific rule."""
        all_configs = self.get_all_configs()
        mapping = {
            "rule1": ["forbidden_words", "exception_words"],
            "rule2": ["forbidden_words", "exception_words"],
            "rule3": ["valid_categories"],
            "rule4": ["meaningless_placeholders"],
            "rule5": ["max_duration_hours"],
            "rule6": ["evaluation_keywords"],
            "rule8": ["empty_content_marker"],
            "global": ["excluded_umu_id", "excluded_lesson_type", "excluded_course_ids"],
        }
        keys = mapping.get(rule_name, [])
        return {k: all_configs.get(k) for k in keys}


@dataclass
class GovernanceStatus:
    """Current status of a governance operation."""

    running: bool = False
    progress: int = 0
    total: int = 0
    message: str = ""
    error: str | None = None
    completed: bool = False
    run_id: str = ""
    current_course: str = ""
    compliant_count: int = 0
    non_compliant_count: int = 0
    major_count: int = 0
    current_course_level: str = ""
    current_course_issues: str = ""

@dataclass
class RuleResult:
    """Result of a single rule check."""

    rule_id: int
    rule_name: str
    compliant: bool  # True = 达标, False = 未达标
    level: str  # "ok", "major", "minor", "unknown"
    issue: str = ""


@dataclass
class CourseGovernanceResult:
    """Complete governance result for a single course."""

    course_id: str
    group_id: str
    course_name: str
    creator_email: str
    creator_name: str
    umu_link: str
    overall_compliant: bool
    overall_level: str
    rule_results: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class GovernanceService:
    """Manages background governance auditing for courses."""

    def __init__(self, database_url: str = DEFAULT_DATABASE_URL):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

        self.config_service = GovernanceConfigService(database_url)
        self.status = GovernanceStatus()
        self._thread: threading.Thread | None = None

        self._recover_interrupted_runs()

    def _recover_interrupted_runs(self) -> None:
        """Mark orphaned 'running' records as interrupted (app was restarted)."""
        db_session = self.SessionLocal()
        try:
            orphaned = db_session.query(GovernanceRun).filter_by(status="running").all()
            for run in orphaned:
                run.status = "interrupted"
                run.error_message = "应用重启导致任务中断"
            if orphaned:
                db_session.commit()
                logger.info("Recovered %d interrupted governance runs", len(orphaned))
        except Exception:
            db_session.rollback()
            logger.exception("Failed to recover interrupted runs")
        finally:
            db_session.close()

    def _client_from_session(self, serialized: str) -> LMSClient:
        """Reconstruct an LMSClient from a serialized session."""
        s = deserialize_session(serialized)
        auth = SessionAuth(session=s)
        return LMSClient(auth=auth)

    def start_governance(
        self, serialized_session: str, start_date: str | None = None, end_date: str | None = None
    ) -> str:
        """Start governance audit in background thread. Returns run_id."""
        if self.status.running:
            return self.status.run_id

        run_id = str(uuid.uuid4())
        self.status = GovernanceStatus(running=True, run_id=run_id)
        self._thread = threading.Thread(
            target=self._run_governance,
            args=(serialized_session, run_id, start_date, end_date),
            daemon=True,
        )
        self._thread.start()
        return run_id

    def _run_governance(
        self, serialized_session: str, run_id: str,
        start_date: str | None = None, end_date: str | None = None,
    ) -> None:
        """Main governance flow: iterate courses and check rules."""
        client: LMSClient | None = None
        db_session = self.SessionLocal()

        try:
            client = self._client_from_session(serialized_session)

            # Create governance run record
            run_record = GovernanceRun(
                run_id=run_id,
                status="running",
                start_date=start_date,
                end_date=end_date,
            )
            db_session.add(run_record)
            db_session.commit()

            # Query courses in scope
            from datetime import datetime as dt

            excluded_umu_id = self.config_service.get_config("excluded_umu_id", "13264912")
            excluded_lesson_type = self.config_service.get_config("excluded_lesson_type", "999")
            query = (
                db_session.query(Course)
                .filter(Course.umu_id != excluded_umu_id)
                .filter(Course.lesson_type != excluded_lesson_type)
            )

            if start_date:
                try:
                    start_dt = dt.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Course.creat_time >= start_dt)
                except (ValueError, TypeError):
                    logger.warning("Invalid start_date format: %s", start_date)

            if end_date:
                try:
                    from datetime import timedelta
                    end_dt = dt.strptime(end_date, "%Y-%m-%d")
                    # Include the full day: next day at 00:00
                    query = query.filter(Course.creat_time < end_dt + timedelta(days=1))
                except (ValueError, TypeError):
                    logger.warning("Invalid end_date format: %s", end_date)

            courses = query.all()

            total = len(courses)
            self.status.total = total
            run_record.total_courses = total
            db_session.commit()

            logger.info("Governance started, run_id=%s, courses=%d", run_id, total)

            processed = 0
            for course in courses:
                self.status.current_course = course.title or course.course_id
                self.status.message = f"正在审核: {self.status.current_course}"

                result = self._check_course(course, client, db_session)
                self._save_result(run_id, result, db_session)

                processed += 1
                self.status.progress = processed

                # Update real-time stats
                if result.overall_compliant:
                    self.status.compliant_count += 1
                else:
                    self.status.non_compliant_count += 1

                if result.overall_level in ("major", "minor", "unknown"):
                    self.status.major_count += 1

                self.status.current_course_level = result.overall_level
                self.status.current_course_issues = "; ".join(result.issues) if result.issues else "合规"

                logger.info(
                    "Governance progress: %d/%d, course=%s, level=%s",
                    processed, total, course.course_id, result.overall_level,
                )

                # Rate limit: sleep between courses
                time.sleep(0.5)

            run_record.status = "completed"
            run_record.completed_at = now_beijing()
            run_record.processed_courses = processed
            db_session.commit()
            self.status.completed = True
            self.status.message = f"治理完成，共审核 {processed} 门课程"
            logger.info("Governance completed, run_id=%s, processed=%d", run_id, processed)

        except Exception as exc:
            logger.exception("Governance failed")
            self.status.error = str(exc)
            self.status.message = f"治理失败: {exc}"
            try:
                db_session.rollback()
                # Try to update run record if it exists
                run_record = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
                if run_record:
                    run_record.status = "failed"
                    run_record.error_message = str(exc)
                    db_session.commit()
            except Exception:
                logger.exception("Failed to save governance run error state")
        finally:
            self.status.running = False
            if client is not None:
                client.close()
            db_session.close()

    def resume_governance(self, run_id: str, serialized_session: str) -> bool:
        """Resume an interrupted governance run. Returns True if started."""
        if self.status.running:
            return False

        # Validate run exists and is resumable
        db_session = self.SessionLocal()
        try:
            run = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
            if not run:
                return False
            if run.status not in ("interrupted", "failed"):
                return False
        finally:
            db_session.close()

        self.status = GovernanceStatus(running=True, run_id=run_id)
        self._thread = threading.Thread(
            target=self._run_governance_resume,
            args=(serialized_session, run_id),
            daemon=True,
        )
        self._thread.start()
        return True

    def _run_governance_resume(self, serialized_session: str, run_id: str) -> None:
        """Resume governance: process only courses not yet audited in this run."""
        client: LMSClient | None = None
        db_session = self.SessionLocal()

        try:
            client = self._client_from_session(serialized_session)

            run_record = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
            if not run_record:
                raise ValueError("运行记录不存在")

            run_record.status = "running"
            run_record.error_message = None
            db_session.commit()

            excluded_umu_id = self.config_service.get_config("excluded_umu_id", "13264912")
            excluded_lesson_type = self.config_service.get_config("excluded_lesson_type", "999")
            query = (
                db_session.query(Course)
                .filter(Course.umu_id != excluded_umu_id)
                .filter(Course.lesson_type != excluded_lesson_type)
            )

            # Apply original date filters stored in run record
            run_start_date = getattr(run_record, "start_date", None)
            run_end_date = getattr(run_record, "end_date", None)

            if run_start_date:
                try:
                    start_dt = datetime.strptime(run_start_date, "%Y-%m-%d")
                    query = query.filter(Course.creat_time >= start_dt)
                except (ValueError, TypeError):
                    logger.warning("Invalid stored start_date: %s", run_start_date)

            if run_end_date:
                try:
                    from datetime import timedelta
                    end_dt = datetime.strptime(run_end_date, "%Y-%m-%d")
                    query = query.filter(Course.creat_time < end_dt + timedelta(days=1))
                except (ValueError, TypeError):
                    logger.warning("Invalid stored end_date: %s", run_end_date)

            courses = query.all()

            total = len(courses)
            self.status.total = total
            run_record.total_courses = total
            db_session.commit()

            # Find already processed course IDs
            existing_results = (
                db_session.query(GovernanceResult.course_id)
                .filter_by(run_id=run_id)
                .all()
            )
            processed_ids = {r.course_id for r in existing_results}

            # Compute baseline stats from existing results
            existing_all = (
                db_session.query(GovernanceResult)
                .filter_by(run_id=run_id)
                .all()
            )
            processed = len(existing_all)
            for r in existing_all:
                if r.overall_compliant:
                    self.status.compliant_count += 1
                else:
                    self.status.non_compliant_count += 1
                if r.overall_level in ("major", "minor", "unknown"):
                    self.status.major_count += 1

            self.status.progress = processed
            self.status.message = f"继续治理，已处理 {processed}/{total} 门课程"
            logger.info(
                "Governance resumed, run_id=%s, total=%d, processed=%d",
                run_id, total, processed,
            )

            for course in courses:
                if course.course_id in processed_ids:
                    continue

                self.status.current_course = course.title or course.course_id
                self.status.message = f"正在审核: {self.status.current_course}"

                result = self._check_course(course, client, db_session)
                self._save_result(run_id, result, db_session)

                processed += 1
                self.status.progress = processed

                if result.overall_compliant:
                    self.status.compliant_count += 1
                else:
                    self.status.non_compliant_count += 1

                if result.overall_level in ("major", "minor", "unknown"):
                    self.status.major_count += 1

                self.status.current_course_level = result.overall_level
                self.status.current_course_issues = "; ".join(result.issues) if result.issues else "合规"

                logger.info(
                    "Governance progress: %d/%d, course=%s, level=%s",
                    processed, total, course.course_id, result.overall_level,
                )

                time.sleep(0.5)

            run_record.status = "completed"
            run_record.completed_at = now_beijing()
            run_record.processed_courses = processed
            db_session.commit()
            self.status.completed = True
            self.status.message = f"治理完成，共审核 {processed} 门课程"
            logger.info("Governance completed, run_id=%s, processed=%d", run_id, processed)

        except Exception as exc:
            logger.exception("Governance resume failed")
            self.status.error = str(exc)
            self.status.message = f"治理失败: {exc}"
            try:
                db_session.rollback()
                run_record = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
                if run_record:
                    run_record.status = "failed"
                    run_record.error_message = str(exc)
                    db_session.commit()
            except Exception:
                logger.exception("Failed to save governance run error state")
        finally:
            self.status.running = False
            if client is not None:
                client.close()
            db_session.close()

    def _check_course(
        self, course: Course, client: LMSClient, db_session: Any
    ) -> CourseGovernanceResult:
        """Execute all 8 governance rules for a single course."""
        course_id = course.course_id or ""
        group_id = course.group_id or ""
        title = course.title or ""

        # Resolve creator info from users table
        creator_email = ""
        creator_name = ""
        if course.umu_id:
            creator = db_session.query(User).filter_by(umu_id=course.umu_id).first()
            if creator:
                creator_email = creator.email or ""
                creator_name = creator.name or ""

        umu_link = f"https://www.umu.cn/course/index#/groups/{course_id}/groupInfo/view"

        # Parse lesson_type as int
        try:
            lesson_type = int(course.lesson_type) if course.lesson_type is not None else None
        except (ValueError, TypeError):
            lesson_type = None

        # Check if course is in exception list
        excluded_course_ids = self.config_service.get_config("excluded_course_ids", [])
        if course_id and excluded_course_ids and str(course_id) in [str(c) for c in excluded_course_ids]:
            return CourseGovernanceResult(
                course_id=course_id,
                group_id=group_id,
                course_name=title,
                creator_email=creator_email,
                creator_name=creator_name,
                umu_link=umu_link,
                overall_compliant=True,
                overall_level="ok",
                rule_results=[self._rule_result_to_dict(
                    RuleResult(rule_id=i, rule_name=f"规则{i}", compliant=True, level="ok", issue="")
                ) for i in range(1, 9)],
                issues=[],
            )

        rule_results: list[RuleResult] = []

        # Rule 1: Course title
        rule_results.append(self._check_rule1_title(title, lesson_type))

        # Rule 2: Course type consistency
        rule_results.append(self._check_rule2_type(title, lesson_type))

        # Rule 3: Content category
        rule_results.append(self._check_rule3_category(course.categoryArr))

        # Rule 4: Course description
        rule_results.append(
            self._check_rule4_description(course.desc, course.multimedia_id, client)
        )

        # Rule 5: Course duration
        rule_results.append(
            self._check_rule5_duration(db_session, group_id)
        )

        # Load sessions from local DB
        sessions = self._get_local_sessions(group_id, db_session)

        # Real-time fetch if missing for all course types
        attempted_fetch = False
        if not sessions:
            logger.info("No local sessions for group_id=%s, fetching from API", group_id)
            fetched = self._fetch_and_save_sessions(client, group_id, db_session)
            attempted_fetch = True
            if fetched:
                sessions = self._get_local_sessions(group_id, db_session)
                logger.info("Fetched %d sessions for group_id=%s", fetched, group_id)

        # If still no sessions after real-time fetch, treat as non-compliant
        if not sessions and attempted_fetch:
            no_session_issue = "没有查询到课程小节"
            # Rule 6: only for lesson_type 1/2
            if lesson_type in (1, 2):
                rule_results.append(
                    RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=False, level="major", issue=no_session_issue)
                )
            # Rule 7: for all course types
            rule_results.append(
                RuleResult(rule_id=7, rule_name="必修小节", compliant=False, level="major", issue=no_session_issue)
            )
            # Rule 8: only for lesson_type 1/2
            if lesson_type in (1, 2):
                rule_results.append(
                    RuleResult(rule_id=8, rule_name="课程课件", compliant=False, level="major", issue=no_session_issue)
                )
        else:
            # Rule 6: Evaluation / exam
            rule_results.append(
                self._check_rule6_evaluation(sessions, lesson_type)
            )

            # Rule 7: Required sections
            rule_results.append(
                self._check_rule7_required(sessions)
            )

            # Rule 8: Course materials
            rule_results.append(
                self._check_rule8_materials(sessions, lesson_type, client)
            )

        # Compute overall result
        levels = [r.level for r in rule_results]
        has_major = any(l == "major" for l in levels)
        has_unknown = any(l == "unknown" for l in levels)
        has_minor = any(l == "minor" for l in levels)

        if has_major:
            overall_level = "major"
            overall_compliant = False
        elif has_unknown:
            overall_level = "unknown"
            overall_compliant = False
        elif has_minor:
            overall_level = "minor"
            overall_compliant = False
        else:
            overall_level = "ok"
            overall_compliant = True

        issues = [r.issue for r in rule_results if r.issue]

        return CourseGovernanceResult(
            course_id=course_id,
            group_id=group_id,
            course_name=title,
            creator_email=creator_email,
            creator_name=creator_name,
            umu_link=umu_link,
            overall_compliant=overall_compliant,
            overall_level=overall_level,
            rule_results=[self._rule_result_to_dict(r) for r in rule_results],
            issues=issues,
        )

    @staticmethod
    def _rule_result_to_dict(r: RuleResult) -> dict:
        return {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "compliant": r.compliant,
            "level": r.level,
            "issue": r.issue,
        }

    # ------------------------------------------------------------------
    # Rule 1: Course title
    # ------------------------------------------------------------------
    def _check_rule1_title(self, title: str, lesson_type: int | None) -> RuleResult:
        """Rule 1: Title should reflect learning content."""
        forbidden_words = set(self.config_service.get_config("forbidden_words", []))
        exception_words = set(self.config_service.get_config("exception_words", []))
        fallback_words = set(self.config_service.get_config("fallback_forbidden_words", []))

        # Fallback rules apply to all lesson_types and ignore exception words
        if title and len(title) < 2:
            return RuleResult(
                rule_id=1,
                rule_name="课程名称",
                compliant=False,
                level="major",
                issue="课程标题字符数不足 2 个",
            )

        fallback_hits = _title_matched_forbidden_words(title, fallback_words)
        if fallback_hits:
            return RuleResult(
                rule_id=1,
                rule_name="课程名称",
                compliant=False,
                level="major",
                issue=f"课程标题包含兜底禁词：{'、'.join(fallback_hits)}",
            )

        # lesson_type = 0 (online) skips the remaining title checks
        if lesson_type == 0:
            return RuleResult(
                rule_id=1,
                rule_name="课程名称",
                compliant=True,
                level="ok",
                issue="",
            )

        # lesson_type in {1, 2, 999}
        forbidden_hits = _title_matched_forbidden_words(title, forbidden_words)
        if not forbidden_hits:
            return RuleResult(rule_id=1, rule_name="课程名称", compliant=True, level="ok", issue="")

        # Hits forbidden word
        if _title_hits_exception(title, exception_words):
            return RuleResult(rule_id=1, rule_name="课程名称", compliant=True, level="ok", issue="")

        return RuleResult(
            rule_id=1,
            rule_name="课程名称",
            compliant=False,
            level="major",
            issue=f"课程名称涉及非培训内容（命中禁词：{'、'.join(forbidden_hits)}）",
        )

    # ------------------------------------------------------------------
    # Rule 2: Course type consistency
    # ------------------------------------------------------------------
    def _check_rule2_type(self, title: str, lesson_type: int | None) -> RuleResult:
        """Rule 2: Course type should be consistent with title."""
        forbidden_words = set(self.config_service.get_config("forbidden_words", []))
        exception_words = set(self.config_service.get_config("exception_words", []))
        forbidden_hits = _title_matched_forbidden_words(title, forbidden_words)
        hits_exception = _title_hits_exception(title, exception_words)

        if lesson_type in (0, 1, 2):
            # Training course
            if forbidden_hits and not hits_exception:
                return RuleResult(
                    rule_id=2,
                    rule_name="课程形式",
                    compliant=False,
                    level="major",
                    issue=f"培训类课程标题包含非培训关键词：{'、'.join(forbidden_hits)}",
                )
            return RuleResult(rule_id=2, rule_name="课程形式", compliant=True, level="ok", issue="")

        if lesson_type == 999:
            # Non-training course
            if not forbidden_hits or hits_exception:
                return RuleResult(
                    rule_id=2,
                    rule_name="课程形式",
                    compliant=True,
                    level="minor",
                    issue="非培训类课程标题疑似与形式错位",
                )
            return RuleResult(rule_id=2, rule_name="课程形式", compliant=True, level="ok", issue="")

        # Unknown lesson_type
        return RuleResult(
            rule_id=2,
            rule_name="课程形式",
            compliant=True,
            level="unknown",
            issue="无法识别课程形式",
        )

    # ------------------------------------------------------------------
    # Rule 3: Content category
    # ------------------------------------------------------------------
    def _check_rule3_category(self, category_arr: Any) -> RuleResult:
        """Rule 3: Must have one of the valid categories."""
        valid_categories = set(self.config_service.get_config("valid_categories", []))
        if not category_arr:
            return RuleResult(
                rule_id=3,
                rule_name="内容分类",
                compliant=False,
                level="major",
                issue="课程缺少通用力/专业力/领导力/新兴力分类",
            )

        names: set[str] = set()
        if isinstance(category_arr, list):
            for item in category_arr:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("categoryName") or ""
                    if name:
                        names.add(name)
                elif isinstance(item, str):
                    names.add(item)
        elif isinstance(category_arr, dict):
            name = category_arr.get("name") or category_arr.get("categoryName") or ""
            if name:
                names.add(name)

        for name in names:
            for valid in valid_categories:
                if valid in name:
                    return RuleResult(rule_id=3, rule_name="内容分类", compliant=True, level="ok", issue="")

        return RuleResult(
            rule_id=3,
            rule_name="内容分类",
            compliant=False,
            level="major",
            issue="课程缺少通用力/专业力/领导力/新兴力分类",
        )

    # ------------------------------------------------------------------
    # Rule 4: Course description
    # ------------------------------------------------------------------
    def _check_rule4_description(
        self, desc: str | None, multimedia_id: str | None, client: LMSClient
    ) -> RuleResult:
        """Rule 4: Description should contain meaningful content.

        Falls back to fulltextinfo API for image-based descriptions when
        the text description is empty, a placeholder, or too short.
        """
        meaningless_placeholders = set(self.config_service.get_config("meaningless_placeholders", []))
        desc_str = (desc or "").strip()

        # Fast path: clearly meaningful text description
        if desc_str and desc_str not in meaningless_placeholders:
            if desc_str.startswith("课程大纲：") and len(desc_str) > len("课程大纲："):
                return RuleResult(rule_id=4, rule_name="课程介绍", compliant=True, level="ok", issue="")
            if len(desc_str) > 4 and desc_str != "课程大纲：":
                return RuleResult(rule_id=4, rule_name="课程介绍", compliant=True, level="ok", issue="")

        # Fallback: check fulltextinfo for image-based description
        if multimedia_id:
            try:
                resp = client.get(
                    "/ajax/multimedia/fulltextinfo",
                    params={"top_section_id": multimedia_id},
                )
                data = resp.get("data", {}) if isinstance(resp, dict) else {}
                content = data.get("content", "") if isinstance(data, dict) else ""
                if content and "<img" in content:
                    return RuleResult(rule_id=4, rule_name="课程介绍", compliant=True, level="ok", issue="")
            except Exception as exc:
                logger.warning("fulltextinfo API failed: %s", exc)

        # Original logic for non-compliant cases
        if not desc_str:
            return RuleResult(
                rule_id=4,
                rule_name="课程介绍",
                compliant=False,
                level="major",
                issue="课程介绍为空且无图片介绍" if not multimedia_id else "课程介绍为空且非图片型介绍",
            )

        if desc_str in meaningless_placeholders:
            return RuleResult(
                rule_id=4,
                rule_name="课程介绍",
                compliant=False,
                level="major",
                issue="课程介绍为无意义占位符",
            )

        # 4 chars or less, not a placeholder
        return RuleResult(
            rule_id=4,
            rule_name="课程介绍",
            compliant=False,
            level="unknown",
            issue="课程介绍内容过短，需人工确认",
        )

    # ------------------------------------------------------------------
    # Rule 5: Course duration
    # ------------------------------------------------------------------
    def _check_rule5_duration(self, db_session: Any, group_id: str) -> RuleResult:
        """Rule 5: Course should have valid duration hours."""
        if not group_id:
            return RuleResult(
                rule_id=5,
                rule_name="课程学时",
                compliant=False,
                level="major",
                issue="课程缺少分组ID，无法判断学时",
            )

        records = (
            db_session.query(CourseGroupTime)
            .filter_by(group_id=group_id)
            .all()
        )

        if not records:
            return RuleResult(
                rule_id=5,
                rule_name="课程学时",
                compliant=False,
                level="major",
                issue="未设置课程学时",
            )

        total_hours = 0.0
        for r in records:
            if r.start_time and r.end_time:
                delta = r.end_time - r.start_time
                total_hours += delta.total_seconds() / 3600.0

        max_duration = self.config_service.get_config("max_duration_hours", 30)
        if total_hours > max_duration:
            return RuleResult(
                rule_id=5,
                rule_name="课程学时",
                compliant=False,
                level="major",
                issue=f"课程学时设置可能错误（{total_hours:.1f}小时）",
            )

        return RuleResult(rule_id=5, rule_name="课程学时", compliant=True, level="ok", issue="")

    # ------------------------------------------------------------------
    # Rule 6: Evaluation / exam
    # ------------------------------------------------------------------
    def _check_rule6_evaluation(
        self, sessions: list[SessionModel], lesson_type: int | None
    ) -> RuleResult:
        """Rule 6: Course should contain evaluation or exam (only for lesson_type 1,2)."""
        if lesson_type not in (1, 2):
            return RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=True, level="ok", issue="")

        if not sessions:
            return RuleResult(
                rule_id=6,
                rule_name="课程评价/考试",
                compliant=True,
                level="unknown",
                issue="缺少小节数据，无法判断",
            )

        # Check for exam session (session_type=10, is_require=1)
        for s in sessions:
            if s.session_type == "10" and s.is_require == 1:
                return RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=True, level="ok", issue="")

        # Check sign-in sessions (session_type=6, is_require=1)
        for s in sessions:
            if s.session_type == "6" and s.is_require == 1:
                if s.type_name == "评价":
                    return RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=True, level="ok", issue="")
                if self._questions_have_evaluation(s.questions):
                    return RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=True, level="ok", issue="")

        # Check questionnaire sessions (session_type=1, is_require=1)
        for s in sessions:
            if s.session_type == "1" and s.is_require == 1:
                if self._questions_have_evaluation(s.questions):
                    return RuleResult(rule_id=6, rule_name="课程评价/考试", compliant=True, level="ok", issue="")

        return RuleResult(
            rule_id=6,
            rule_name="课程评价/考试",
            compliant=False,
            level="major",
            issue="课程缺少评价或考试小节",
        )

    def _questions_have_evaluation(self, questions: Any) -> bool:
        """Check if any question title contains evaluation keywords."""
        evaluation_keywords = set(self.config_service.get_config("evaluation_keywords", []))
        if not questions:
            return False
        if not isinstance(questions, list):
            return False
        for q in questions:
            title = self._extract_question_title(q)
            if not title:
                continue
            for kw in evaluation_keywords:
                if kw in title:
                    return True
        return False

    @staticmethod
    def _extract_question_title(question: Any) -> str:
        """Extract title from a question dict with various nested formats."""
        if isinstance(question, str):
            return question
        if not isinstance(question, dict):
            return ""
        # Direct fields
        title = question.get("title") or question.get("question") or question.get("name") or ""
        if title:
            return title
        # Nested questionInfo (e.g., sign-in sessions)
        info = question.get("questionInfo", {})
        if isinstance(info, dict):
            title = (
                info.get("questionTitle")
                or info.get("title")
                or info.get("question")
                or info.get("name")
                or ""
            )
            if title:
                return title
        # Deeper nested setup
        setup = question.get("setup", {})
        if isinstance(setup, dict):
            return setup.get("title") or setup.get("question") or setup.get("name") or ""
        return ""

    # ------------------------------------------------------------------
    # Rule 7: Required sections
    # ------------------------------------------------------------------
    def _check_rule7_required(self, sessions: list[SessionModel]) -> RuleResult:
        """Rule 7: Not all sessions should be optional."""
        if not sessions:
            return RuleResult(
                rule_id=7,
                rule_name="必修小节",
                compliant=True,
                level="unknown",
                issue="缺少小节数据，无法判断",
            )

        all_optional = all(s.is_require == 0 for s in sessions)
        if all_optional:
            return RuleResult(
                rule_id=7,
                rule_name="必修小节",
                compliant=False,
                level="major",
                issue="所有小节均为选修",
            )

        return RuleResult(rule_id=7, rule_name="必修小节", compliant=True, level="ok", issue="")

    # ------------------------------------------------------------------
    # Rule 8: Course materials
    # ------------------------------------------------------------------
    def _check_rule8_materials(
        self,
        sessions: list[SessionModel],
        lesson_type: int | None,
        client: LMSClient,
    ) -> RuleResult:
        """Rule 8: Course should have uploaded materials (only for lesson_type 1,2)."""
        if lesson_type not in (1, 2):
            return RuleResult(rule_id=8, rule_name="课程课件", compliant=True, level="ok", issue="")

        if not sessions:
            return RuleResult(
                rule_id=8,
                rule_name="课程课件",
                compliant=False,
                level="major",
                issue="缺少小节数据，无法判断课件",
            )

        # Fallback: article (13) or image-text (15) sessions count as materials
        if any(s.session_type in ("13", "15") for s in sessions):
            return RuleResult(rule_id=8, rule_name="课程课件", compliant=True, level="ok", issue="")

        # Filter document sessions (session_type=14)
        doc_sessions = [s for s in sessions if s.session_type == "14"]
        if not doc_sessions:
            return RuleResult(
                rule_id=8,
                rule_name="课程课件",
                compliant=False,
                level="major",
                issue="课程未上传课件（无文档小节）",
            )

        # Check each document session via API
        empty_content_marker = self.config_service.get_config("empty_content_marker", EMPTY_CONTENT_MARKER)
        has_valid_material = False
        for s in doc_sessions:
            try:
                resp = client.get(f"/uapi/v1/element/{s.session_id}")
                raw = resp.get("data", resp) if isinstance(resp, dict) else resp
                raw_str = str(raw)
                if empty_content_marker not in raw_str:
                    has_valid_material = True
                    break
            except Exception as exc:
                logger.warning("Failed to check element %s: %s", s.session_id, exc)
                continue

        if has_valid_material:
            return RuleResult(rule_id=8, rule_name="课程课件", compliant=True, level="ok", issue="")

        return RuleResult(
            rule_id=8,
            rule_name="课程课件",
            compliant=False,
            level="major",
            issue="课程未上传有效课件",
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    @staticmethod
    def _get_local_sessions(group_id: str, db_session: Any) -> list[SessionModel]:
        """Query pre-synced session data from local database.

        Sessions for lesson_type 1/2 courses are fetched during course sync
        (see sync_service.py:_sync_courses). Rules 6,7,8 operate on this
        local data without additional API calls.
        """
        if not group_id:
            return []
        return db_session.query(SessionModel).filter_by(course_id=group_id).all()

    # ------------------------------------------------------------------
    # Real-time session fetch
    # ------------------------------------------------------------------
    def _fetch_and_save_sessions(
        self, client: LMSClient, group_id: str, db_session: Any
    ) -> int:
        """Fetch sessions from API and persist. Returns saved count."""
        if not group_id:
            return 0
        items = self._fetch_session_list(client, group_id)
        records = self._collect_session_records(items, group_id)
        for cid in self._extract_chapter_ids(items):
            chapter_items = self._fetch_chapter_items(client, group_id, cid)
            records.extend(self._collect_session_records(chapter_items, group_id, cid))
        if records:
            self._upsert_sessions(records, db_session)
        return len(records)

    def _fetch_session_list(self, client: LMSClient, group_id: str) -> list[dict]:
        """Fetch top-level session list from API."""
        try:
            result = client.get(
                "/ajax/session/getsessionlistbygroup",
                params={
                    "group_id": group_id,
                    "isFirstLoad": "true",
                    "is_contain_chapter": 1,
                    "page": 1,
                    "size": 500,
                    "status_str": "0,1",
                },
            )
            data = result.get("data", {}) if isinstance(result, dict) else {}
            return data.get("list", []) if isinstance(data, dict) else []
        except Exception as exc:
            logger.warning("Failed to fetch sessions for %s: %s", group_id, exc)
            return []

    @staticmethod
    def _extract_chapter_ids(items: list[dict]) -> list[str]:
        """Extract chapter container IDs from session list items."""
        ids: list[str] = []
        for item in items:
            if item.get("item_type") == 2 or str(item.get("item_type")) == "2":
                cid = str(item.get("id", ""))
                if cid:
                    ids.append(cid)
        return ids

    def _fetch_chapter_items(
        self, client: LMSClient, group_id: str, chapter_id: str
    ) -> list[dict]:
        """Fetch sessions within a chapter."""
        try:
            result = client.get(
                "/ajax/session/getsessionlistbygroup",
                params={
                    "group_id": group_id,
                    "chapter_id": chapter_id,
                    "page": 1,
                    "size": 500,
                    "status_str": "0,1",
                },
            )
            data = result.get("data", {}) if isinstance(result, dict) else {}
            return data.get("list", []) if isinstance(data, dict) else []
        except Exception as exc:
            logger.warning("Failed to fetch chapter %s: %s", chapter_id, exc)
            return []

    def _collect_session_records(
        self, items: list[dict], group_id: str, chapter_id: str = ""
    ) -> list[dict]:
        """Build session records from API items."""
        records: list[dict] = []
        for item in items:
            record = self._build_session_record(item, group_id, chapter_id)
            if record:
                records.append(record)
        return records

    @staticmethod
    def _build_session_record(
        item: dict, course_id: str, chapter_id: str = ""
    ) -> dict | None:
        """Transform API item into session record."""
        info = item.get("sessionInfo", {})
        if not info:
            return None
        setup = info.get("setup", {})
        return {
            "session_id": str(info.get("sessionId", "")),
            "course_id": course_id,
            "chapter_id": chapter_id if chapter_id else str(info.get("chapter_id", "")),
            "name": info.get("sessionTitle", ""),
            "status": int(info.get("status", 0)) if info.get("status") is not None else 1,
            "session_type": str(info.get("sessionType", "")),
            "is_require": 1 if info.get("is_require") else 0,
            "type_name": setup.get("type_name") or setup.get("typeName") or "",
            "questions": item.get("questionArr"),
            "raw_data": item,
        }

    def _upsert_sessions(self, records: list[dict], db_session: Any) -> None:
        """Upsert session records into database."""
        for record in records:
            sid = record.get("session_id")
            if not sid:
                continue
            existing = db_session.query(SessionModel).filter_by(session_id=sid).first()
            if existing:
                for key, value in record.items():
                    if key != "raw_data":
                        setattr(existing, key, value)
                existing.raw_data = record["raw_data"]
            else:
                db_session.add(SessionModel(**record))
        db_session.commit()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_result(
        self, run_id: str, result: CourseGovernanceResult, db_session: Any
    ) -> None:
        """Save a single course governance result."""
        gr = GovernanceResult(
            run_id=run_id,
            course_id=result.course_id,
            group_id=result.group_id,
            course_name=result.course_name,
            creator_email=result.creator_email,
            creator_name=result.creator_name,
            umu_link=result.umu_link,
            overall_compliant=result.overall_compliant,
            overall_level=result.overall_level,
            rule_results=result.rule_results,
            issues=result.issues,
        )
        db_session.add(gr)
        db_session.commit()

    def preview_governance(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, Any]:
        """Return preview stats for a date range without running governance."""
        db_session = self.SessionLocal()
        try:
            excluded_umu_id = self.config_service.get_config("excluded_umu_id", "13264912")
            excluded_lesson_type = self.config_service.get_config("excluded_lesson_type", "999")
            query = (
                db_session.query(Course)
                .filter(Course.umu_id != excluded_umu_id)
                .filter(Course.lesson_type != excluded_lesson_type)
            )

            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Course.creat_time >= start_dt)
                except (ValueError, TypeError):
                    logger.warning("Invalid start_date format: %s", start_date)

            if end_date:
                try:
                    from datetime import timedelta
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    query = query.filter(Course.creat_time < end_dt + timedelta(days=1))
                except (ValueError, TypeError):
                    logger.warning("Invalid end_date format: %s", end_date)

            course_count = query.count()
            user_count = db_session.query(User).count()

            # Approximate last sync time from most recent course update_time
            last_course = (
                db_session.query(Course)
                .order_by(Course.update_time.desc())
                .first()
            )
            last_sync = None
            if last_course and last_course.update_time:
                last_sync = last_course.update_time.isoformat()

            return {
                "course_count": course_count,
                "user_count": user_count,
                "last_sync": last_sync,
            }
        finally:
            db_session.close()

    def get_runs(self) -> list[dict]:
        """Return all governance runs ordered by start time desc."""
        db_session = self.SessionLocal()
        try:
            runs = (
                db_session.query(GovernanceRun)
                .order_by(GovernanceRun.started_at.desc())
                .all()
            )
            result = []
            for r in runs:
                # Compute compliant rate from stored results
                compliant_rate: int | None = None
                if r.status in ("completed", "interrupted") and r.total_courses:
                    compliant_count = (
                        db_session.query(GovernanceResult)
                        .filter_by(run_id=r.run_id, overall_compliant=True)
                        .count()
                    )
                    compliant_rate = round((compliant_count / r.total_courses) * 100)

                result.append(
                    {
                        "run_id": r.run_id,
                        "started_at": r.started_at.isoformat() if r.started_at else None,
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                        "total_courses": r.total_courses,
                        "processed_courses": r.processed_courses,
                        "status": r.status,
                        "error_message": r.error_message,
                        "start_date": r.start_date,
                        "end_date": r.end_date,
                        "compliant_rate": compliant_rate,
                    }
                )
            return result
        finally:
            db_session.close()

    def get_results(self, run_id: str) -> dict:
        """Return results and stats for a governance run."""
        db_session = self.SessionLocal()
        try:
            run = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
            if not run:
                return {"run": None, "results": [], "stats": {}}

            results = (
                db_session.query(GovernanceResult)
                .filter_by(run_id=run_id)
                .all()
            )

            total = len(results)
            compliant = sum(1 for r in results if r.overall_compliant)
            major = sum(
                1 for r in results if r.overall_level in ("major", "minor", "unknown")
            )

            return {
                "run": {
                    "run_id": run.run_id,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "total_courses": run.total_courses,
                    "processed_courses": run.processed_courses,
                    "status": run.status,
                    "error_message": run.error_message,
                },
                "results": [
                    {
                        "course_id": r.course_id,
                        "course_name": r.course_name,
                        "creator_email": r.creator_email,
                        "creator_name": r.creator_name,
                        "umu_link": r.umu_link,
                        "overall_compliant": r.overall_compliant,
                        "overall_level": r.overall_level,
                        "rule_results": r.rule_results,
                        "issues": r.issues,
                    }
                    for r in results
                ],
                "stats": {
                    "total": total,
                    "compliant": compliant,
                    "major": major,
                },
            }
        finally:
            db_session.close()

    def delete_run(self, run_id: str) -> bool:
        """Delete a single governance run and its results. Returns True if deleted."""
        db_session = self.SessionLocal()
        try:
            run = db_session.query(GovernanceRun).filter_by(run_id=run_id).first()
            if not run:
                return False
            db_session.query(GovernanceResult).filter_by(run_id=run_id).delete()
            db_session.delete(run)
            db_session.commit()
            # Reset current selection if deleting the active run
            if self.status.run_id == run_id:
                self.status = GovernanceStatus()
            return True
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    def clear_all_runs(self) -> int:
        """Delete all governance runs and results. Returns deleted run count."""
        db_session = self.SessionLocal()
        try:
            db_session.query(GovernanceResult).delete()
            count = db_session.query(GovernanceRun).delete()
            db_session.commit()
            self.status = GovernanceStatus()
            return count
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()
