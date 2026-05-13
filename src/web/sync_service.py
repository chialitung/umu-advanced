"""Background sync service for UMU Advanced."""

from __future__ import annotations

import base64
import logging
import os
import pickle
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from lms_client.auth import SessionAuth
from lms_client.client import LMSClient
from lms_client.storage.models import Base, Course, CourseGroupTime, Session as SessionModel, User
from lms_client.timeutil import now_beijing, timestamp_to_beijing

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DATABASE_URL = f"sqlite:///{os.path.join(_PROJECT_ROOT, 'lms.db')}"


def serialize_session(session: requests.Session) -> str:
    """Serialize session cookies to a base64-encoded string."""
    cookies = session.cookies.get_dict()
    return base64.b64encode(pickle.dumps(cookies)).decode("ascii")


def deserialize_session(pickled: str) -> requests.Session:
    """Reconstruct a session from serialized cookies.

    NOTE: Input is trusted -- data is produced exclusively by
    serialize_session() from an authenticated requests.Session.
    Never call this on untrusted / user-supplied input.
    """
    cookies = pickle.loads(base64.b64decode(pickled))
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value)
    return session


@dataclass
class SyncStatus:
    """Current status of a sync operation."""

    running: bool = False
    progress: int = 0
    total: int = 0
    message: str = ""
    error: str | None = None
    completed: bool = False


class SyncService:
    """Manages background sync operations for users and courses."""

    def __init__(self, database_url: str = DEFAULT_DATABASE_URL):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        self._ensure_columns()

        self.user_status = SyncStatus()
        self.course_status = SyncStatus()
        self._user_thread: threading.Thread | None = None
        self._course_thread: threading.Thread | None = None

    def _ensure_columns(self) -> None:
        """Add missing columns to existing SQLite tables (no-migration path)."""
        if not self.database_url.startswith("sqlite"):
            return
        from sqlalchemy import inspect
        inspector = inspect(self.engine)
        if "chapter_id" not in {c["name"] for c in inspector.get_columns("sessions")}:
            with self.engine.connect() as conn:
                conn.execute("ALTER TABLE sessions ADD COLUMN chapter_id VARCHAR(64)")
                conn.commit()
            logger.info("Added missing column chapter_id to sessions table")

    def _client_from_session(self, serialized: str) -> LMSClient:
        """Reconstruct an LMSClient from a serialized session."""
        session = deserialize_session(serialized)
        auth = SessionAuth(session=session)
        return LMSClient(auth=auth)

    def _transform_user(self, raw: dict) -> dict:
        """Transform API user dict to DB record format."""
        departments = raw.get("departments")
        # UMU API may use different field names for user ID
        umu_id = raw.get("id") or raw.get("user_id") or raw.get("umu_id")
        return {
            "raw_data": raw,
            "umu_id": str(umu_id) if umu_id else "",
            "number": raw.get("number"),
            "user_name": raw.get("user_name"),
            "name": raw.get("user_name") or raw.get("name"),
            "email": raw.get("email"),
            "mobile": raw.get("mobile"),
            "account_joining_time": timestamp_to_beijing(raw.get("account_joining_time")),
            "departments": departments if isinstance(departments, str) else None,
            "role_type": str(raw.get("role_type", "")),
        }

    def _transform_course(self, raw: dict) -> dict:
        """Transform API course dict to DB record format."""
        # Extract group_times if present in raw data
        # UMU API uses "group_time" (singular) in getReportGroupList response
        group_times = (
            raw.get("group_times")
            or raw.get("groupTimes")
            or raw.get("scheduleList")
            or raw.get("group_time")
        )
        if isinstance(group_times, dict):
            group_times = [group_times]

        # UMU API always returns "id"; "group_id" is sometimes absent for
        # newly-created courses. When both exist they're equal, so use id.
        course_id_value = raw.get("id") or raw.get("group_id")
        course_id_str = str(course_id_value) if course_id_value else ""

        return {
            "raw_data": raw,
            "course_id": course_id_str,
            "group_id": course_id_str,
            "title": raw.get("title"),
            "name": raw.get("title") or raw.get("name"),
            "creat_time": timestamp_to_beijing(raw.get("creat_time")),
            "source": raw.get("source"),
            "desc": raw.get("desc"),
            "update_time": timestamp_to_beijing(raw.get("update_time")),
            "head_img_old": raw.get("head_img"),
            "head_img_new": raw.get("head_img"),
            "lesson_type": raw.get("lesson_type"),
            "group_time": timestamp_to_beijing(raw.get("group_time")),
            "umu_id": raw.get("umu_id"),
            "share_url": raw.get("share_url"),
            "access_code": raw.get("access_code"),
            "categoryArr": raw.get("categoryArr"),
            "multimedia_id": raw.get("multimedia_id"),
            "group_times": group_times if isinstance(group_times, list) else None,
        }

    def start_sync_users(self, serialized_session: str) -> None:
        """Start user sync in background thread."""
        if self.user_status.running:
            return
        self.user_status = SyncStatus(running=True)
        self._user_thread = threading.Thread(
            target=self._sync_users,
            args=(serialized_session,),
            daemon=True,
        )
        self._user_thread.start()

    def _sync_users(self, serialized_session: str) -> None:
        """Internal user sync implementation.

        The UMU API requires *is_manager* param. We sync both
        is_manager=0 (regular users) and is_manager=1 (managers)
        to get the full enterprise user list.

        Pagination uses total_page_num from page_info to avoid data loss.
        """
        client = self._client_from_session(serialized_session)
        status = self.user_status
        batch_size = 1000

        try:
            processed = 0
            status.total = 0

            for is_mgr in (0, 1):
                mgr_label = "管理员" if is_mgr else "普通用户"
                if is_mgr > 0:
                    time.sleep(1.0)

                # First call with actual batch size to get data + page_info
                first_resp = client.get(
                    "/ajax/enterprise/getUserList",
                    params={"page": 1, "size": batch_size, "is_manager": is_mgr},
                )
                first_data = first_resp.get("data", {}) if isinstance(first_resp, dict) else {}
                first_items = first_data.get("list", []) if isinstance(first_data, dict) else []
                page_info = first_data.get("page_info", {}) if isinstance(first_data, dict) else {}
                total_page_num = int(page_info.get("total_page_num", 0))
                list_total_num = int(page_info.get("list_total_num", 0))
                status.total += list_total_num

                logger.info(
                    "User sync [%s] started, total=%d, total_page_num=%d",
                    mgr_label, list_total_num, total_page_num,
                )

                if first_items:
                    logger.info(
                        "[%s] First item keys: %s", mgr_label, list(first_items[0].keys())
                    )

                # Process page 1 (already fetched)
                if first_items:
                    records = [self._transform_user(item) for item in first_items]
                    self._upsert_users(records)
                    processed += len(first_items)
                    status.progress = processed
                    status.message = f"已更新 {processed} / {status.total} 用户"

                # Fetch remaining pages up to total_page_num
                for page in range(2, total_page_num + 1):
                    time.sleep(1.0)
                    result = client.get(
                        "/ajax/enterprise/getUserList",
                        params={"page": page, "size": batch_size, "is_manager": is_mgr},
                    )
                    data = result.get("data", {}) if isinstance(result, dict) else {}
                    items = data.get("list", []) if isinstance(data, dict) else []
                    if items:
                        records = [self._transform_user(item) for item in items]
                        self._upsert_users(records)
                        processed += len(items)
                        status.progress = processed
                        status.message = f"已更新 {processed} / {status.total} 用户"

            status.completed = True
            status.message = f"用户同步完成，共 {processed} 条"
            logger.info("User sync completed, processed=%d", processed)
        except Exception as exc:
            logger.exception("User sync failed")
            status.error = str(exc)
            status.message = f"同步失败: {exc}"
        finally:
            status.running = False
            client.close()

    def _upsert_users(self, records: list[dict]) -> None:
        """Upsert users into database."""
        session = self.SessionLocal()
        try:
            skipped = 0
            inserted = 0
            updated = 0
            for record in records:
                umu_id = record.get("umu_id")
                if not umu_id:
                    skipped += 1
                    continue

                existing = session.query(User).filter_by(umu_id=umu_id).first()
                if existing:
                    for key, value in record.items():
                        if key != "raw_data":
                            setattr(existing, key, value)
                    existing.raw_data = record["raw_data"]
                    updated += 1
                else:
                    session.add(User(**record))
                    inserted += 1
            session.commit()
            logger.info("Users upsert: inserted=%d, updated=%d, skipped=%d", inserted, updated, skipped)
        except Exception as exc:
            session.rollback()
            logger.exception("Users upsert failed")
            raise
        finally:
            session.close()

    def start_sync_courses(
        self, serialized_session: str, start_date: str | None = None, end_date: str | None = None
    ) -> None:
        """Start course sync in background thread."""
        if self.course_status.running:
            return
        self.course_status = SyncStatus(running=True)
        self._course_thread = threading.Thread(
            target=self._sync_courses,
            args=(serialized_session, start_date, end_date),
            daemon=True,
        )
        self._course_thread.start()

    def _sync_courses(
        self, serialized_session: str, start_date: str | None = None, end_date: str | None = None
    ) -> None:
        """Internal course sync implementation."""
        client = self._client_from_session(serialized_session)
        status = self.course_status

        # Build date filter params
        # UMU API expects both snake_case strings and camelCase timestamps
        date_params: dict[str, Any] = {}
        if start_date:
            try:
                begin_dt = datetime.strptime(start_date, "%Y-%m-%d")
                date_params["start_day"] = start_date
                date_params["startDay"] = int(begin_dt.timestamp() * 1000)
            except (ValueError, TypeError):
                logger.warning("Invalid start_date format: %s", start_date)
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                date_params["end_day"] = end_date
                date_params["endDay"] = int(end_dt.timestamp() * 1000)
            except (ValueError, TypeError):
                logger.warning("Invalid end_date format: %s", end_date)

        try:
            # First call with actual size=500 to get both data and page_info.
            # page_info contains current_page, list_total_num, size, total_page_num.
            batch_size = 500
            first_page_params: dict[str, Any] = {"page": 1, "size": batch_size, **date_params}
            first_page = client.get(
                "/ajax/enterprise/getReportGroupList",
                params=first_page_params,
            )
            data = first_page.get("data", {})
            page_info = data.get("page_info", {}) if isinstance(data, dict) else {}
            total = int(page_info.get("list_total_num", 0))
            total_page_num = int(page_info.get("total_page_num", 0))
            status.total = total
            logger.info(
                "Course sync started, total=%d, total_page_num=%d, date_params=%s",
                total, total_page_num, date_params,
            )

            processed = 0
            saved = 0

            def _process_page(page_data: dict, page_num: int) -> None:
                nonlocal processed, saved
                items = page_data.get("list", []) if isinstance(page_data, dict) else []
                if not items:
                    return

                if page_num == 1 and items:
                    logger.info("First course item keys: %s", list(items[0].keys()))

                records = [self._transform_course(item) for item in items]

                # Upsert courses and get list of courses needing session sync
                session_sync_ids, page_saved = self._upsert_courses(records, status)

                # Sync sessions for lesson_type 1,2 courses that have been modified
                for idx, group_id in enumerate(session_sync_ids, 1):
                    status.message = (
                        f"接口返回 {processed + len(items)} / {total} 课程，"
                        f"入库 {saved + page_saved} 条，"
                        f"正在同步小节 {idx}/{len(session_sync_ids)}"
                    )
                    self.fetch_and_save_sessions(client, group_id)
                    if idx < len(session_sync_ids):
                        time.sleep(0.5)

                processed += len(items)
                saved += page_saved
                status.progress = processed
                status.message = (
                    f"接口返回 {processed} / {total} 课程，入库 {saved} 条"
                )

            # Process page 1 (already fetched)
            _process_page(data, 1)

            # Fetch remaining pages up to total_page_num
            for page in range(2, total_page_num + 1):
                time.sleep(1.0)
                result = client.get(
                    "/ajax/enterprise/getReportGroupList",
                    params={"page": page, "size": batch_size, **date_params},
                )
                page_data = result.get("data", {}) if isinstance(result, dict) else {}
                _process_page(page_data, page)

            status.completed = True
            status.message = (
                f"课程同步完成，接口返回 {processed} 条，入库 {saved} 条"
            )
            logger.info(
                "Course sync completed, processed=%d, saved=%d", processed, saved
            )
        except Exception as exc:
            logger.exception("Course sync failed")
            status.error = str(exc)
            status.message = f"同步失败: {exc}"
        finally:
            status.running = False
            client.close()

    def _upsert_courses(self, records: list[dict], status: SyncStatus) -> tuple[list[str], int]:
        """Upsert courses into database, handling image downloads.

        Returns (session_sync_ids, saved_count). saved_count is the number of
        rows actually inserted or updated (excludes records skipped due to
        empty course_id).
        """
        session = self.SessionLocal()
        session_sync_ids: list[str] = []
        try:
            skipped = 0
            inserted = 0
            updated = 0

            # Batch query existing courses to avoid N+1 queries
            course_ids = [r.get("course_id") for r in records if r.get("course_id")]
            existing_courses = {
                c.course_id: c
                for c in session.query(Course).filter(Course.course_id.in_(course_ids)).all()
            }

            for record in records:
                course_id = record.get("course_id")
                if not course_id:
                    raw = record.get("raw_data") or {}
                    logger.warning(
                        "Skipping course with empty course_id: raw_id=%s title=%s",
                        raw.get("id"), raw.get("title"),
                    )
                    skipped += 1
                    continue

                # Save group_time data if present
                group_times = record.pop("group_times", None)
                if group_times:
                    self._save_group_times(session, course_id, group_times)

                existing = existing_courses.get(course_id)
                head_img_new = record.get("head_img_new")
                lesson_type = record.get("lesson_type")
                group_id = record.get("group_id")
                update_time = record.get("update_time")

                if existing:
                    for key, value in record.items():
                        if key != "raw_data" or value is not None:
                            setattr(existing, key, value)

                    # Determine if session sync is needed based on update_time
                    if group_id:
                        last_fetch = existing.last_fetch_time
                        if not last_fetch or not update_time or update_time > last_fetch:
                            session_sync_ids.append(group_id)
                        else:
                            logger.info(
                                "Skipping session sync for %s (update_time=%s <= last_fetch=%s)",
                                group_id, update_time, last_fetch
                            )

                    existing.last_fetch_time = now_beijing()
                    updated += 1
                else:
                    # New course always needs session sync
                    if group_id:
                        session_sync_ids.append(group_id)

                    record["last_fetch_time"] = now_beijing()
                    session.add(Course(**record))
                    inserted += 1
            session.commit()
            logger.info(
                "Courses upsert: inserted=%d, updated=%d, skipped=%d, session_sync=%d",
                inserted, updated, skipped, len(session_sync_ids)
            )
        except Exception as exc:
            session.rollback()
            logger.exception("Courses upsert failed")
            raise
        finally:
            session.close()

        return session_sync_ids, inserted + updated

    def _save_group_times(self, session: Any, group_id: str, group_times: list[dict]) -> None:
        """Save or update course group time records."""
        # Delete existing records for this group_id
        session.query(CourseGroupTime).filter_by(group_id=group_id).delete()

        for gt in group_times:
            start_str = gt.get("startTime", "")
            end_str = gt.get("endTime", "")
            group_day = gt.get("groupDay", "")

            start_dt = self._parse_group_time(group_day, start_str)
            end_dt = self._parse_group_time(group_day, end_str)

            if start_dt and end_dt:
                session.add(CourseGroupTime(
                    group_id=group_id,
                    start_time=start_dt,
                    end_time=end_dt,
                ))

    def _parse_group_time(self, group_day: str, time_str: str) -> datetime | None:
        """Parse group_day + time_str into a datetime object."""
        if not group_day or not time_str:
            return None
        try:
            from datetime import time as dt_time
            date_part = datetime.strptime(group_day, "%Y-%m-%d").date()
            hour, minute = map(int, time_str.split(":"))
            t = dt_time(hour, minute)
            return datetime.combine(date_part, t)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _build_session_record(item: dict, course_id: str, chapter_id: str = "") -> dict | None:
        """Transform a single API list item into a session record dict.

        Returns None if the item has no sessionInfo (e.g. a chapter container).
        """
        info = item.get("sessionInfo", {})
        if not info:
            logger.debug("Skipping item without sessionInfo: keys=%s", list(item.keys()))
            return None
        setup = info.get("setup", {})
        record = {
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
        logger.debug(
            "Built record: session_id=%s chapter_id=%s type=%s name=%s",
            record["session_id"], record["chapter_id"], record["session_type"], record["name"],
        )
        return record

    def fetch_and_save_sessions(self, client: LMSClient, group_id: str) -> list[dict]:
        """Fetch sessions for a course from UMU API and save to database.

        Handles chapters: the initial call with is_contain_chapter=1 returns
        both sessions and chapter containers (item_type=2). Each chapter
        requires a second API call to fetch its contained sessions.
        """
        logger.info("Fetching sessions for group_id=%s", group_id)
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
            items = data.get("list", []) if isinstance(data, dict) else []
        except Exception as exc:
            logger.warning("Failed to fetch sessions for group_id=%s: %s", group_id, exc)
            return []

        records: list[dict] = []
        chapter_ids: list[str] = []

        for item in items:
            item_type = item.get("item_type")
            if item_type == 2 or str(item_type) == "2":
                cid = str(item.get("id", ""))
                if cid:
                    chapter_ids.append(cid)
                continue
            record = self._build_session_record(item, group_id)
            if record:
                records.append(record)

        logger.info("Found %d chapter containers for group_id=%s: %s", len(chapter_ids), group_id, chapter_ids)

        for chapter_id in chapter_ids:
            try:
                chapter_result = client.get(
                    "/ajax/session/getsessionlistbygroup",
                    params={
                        "group_id": group_id,
                        "chapter_id": chapter_id,
                        "page": 1,
                        "size": 500,
                        "status_str": "0,1",
                    },
                )
                chapter_data = chapter_result.get("data", {}) if isinstance(chapter_result, dict) else {}
                chapter_items = chapter_data.get("list", []) if isinstance(chapter_data, dict) else []
                logger.info(
                    "Chapter %s API returned %d items for group_id=%s",
                    chapter_id, len(chapter_items), group_id,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch chapter %s sessions for group_id=%s: %s", chapter_id, group_id, exc
                )
                continue

            for idx, item in enumerate(chapter_items):
                record = self._build_session_record(item, group_id, chapter_id=chapter_id)
                if record:
                    logger.debug(
                        "Built chapter session record: session_id=%s chapter_id=%s name=%s",
                        record.get("session_id"), record.get("chapter_id"), record.get("name"),
                    )
                    records.append(record)
                else:
                    logger.warning(
                        "Chapter item %d has no sessionInfo (chapter_id=%s, keys=%s)",
                        idx, chapter_id, list(item.keys()),
                    )

        if records:
            self._upsert_sessions(records)

        logger.info("Fetched %d sessions (%d chapters) for group_id=%s", len(records), len(chapter_ids), group_id)
        return records

    def _upsert_sessions(self, records: list[dict]) -> None:
        """Upsert session records into database."""
        session = self.SessionLocal()
        inserted = 0
        updated = 0
        try:
            for record in records:
                session_id = record.get("session_id")
                if not session_id:
                    logger.warning("Skipping record with empty session_id: name=%s", record.get("name"))
                    continue
                existing = session.query(SessionModel).filter_by(session_id=session_id).first()
                if existing:
                    logger.debug(
                        "Updating session %s (chapter_id=%s -> %s)",
                        session_id, existing.chapter_id, record.get("chapter_id"),
                    )
                    for key, value in record.items():
                        if key != "raw_data":
                            setattr(existing, key, value)
                    existing.raw_data = record["raw_data"]
                    updated += 1
                else:
                    logger.debug(
                        "Inserting session %s (chapter_id=%s, name=%s)",
                        session_id, record.get("chapter_id"), record.get("name"),
                    )
                    session.add(SessionModel(**record))
                    inserted += 1
            session.commit()
            logger.info("Sessions upserted: %d inserted, %d updated, %d total", inserted, updated, len(records))
        except Exception as exc:
            session.rollback()
            logger.exception("Sessions upsert failed")
            raise
        finally:
            session.close()
