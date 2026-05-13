"""Flask application for UMU Advanced."""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Any

import pandas as pd

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session, url_for

from lms_client.auth import UMUSessionAuth
from lms_client.endpoints import UserEndpoint

from lms_client.storage.database import DatabaseManager
from lms_client.timeutil import now_beijing

from .governance_service import GovernanceConfigService, GovernanceService
from .sync_service import SyncService, serialize_session

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
logger = logging.getLogger(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY environment variable is required. "
        "Set it before starting the application."
    )

sync_service = SyncService()
governance_service = GovernanceService()

# Run lightweight column migration on startup (adds missing columns to existing tables)
try:
    db_manager = DatabaseManager()
    db_manager.migrate_columns()
except Exception as exc:
    logger.warning("Database migration failed: %s", exc)


def _create_client_from_session() -> tuple[Any, UserEndpoint] | None:
    """Reconstruct LMSClient and UserEndpoint from Flask session."""
    serialized = session.get("umu_session")
    if not serialized:
        return None

    from lms_client.auth import SessionAuth
    from lms_client.client import LMSClient

    from .sync_service import deserialize_session

    s = deserialize_session(serialized)
    auth = SessionAuth(session=s)
    client = LMSClient(auth=auth)
    return client, UserEndpoint(client)


@app.route("/")
def index() -> Response:
    """Redirect to app if logged in, otherwise to login page."""
    if session.get("logged_in"):
        return redirect(url_for("app_page"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page() -> str:
    """Render login page."""
    return render_template("login.html")


@app.route("/app")
def app_page() -> Response | str:
    """Render main application page."""
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template("app.html")


@app.route("/api/login", methods=["POST"])
def api_login() -> Response:
    """Authenticate with UMU and establish session."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "账号和密码不能为空"}), 400

    auth = UMUSessionAuth(username=username, password=password)
    try:
        auth.login()
    except Exception as exc:
        return jsonify({"success": False, "error": "账号或密码错误"}), 401

    # Check admin status
    client = auth.session
    # We need a proper client to call endpoints
    from lms_client.client import LMSClient

    lms_client = LMSClient(auth=auth)
    user_endpoint = UserEndpoint(lms_client)
    is_admin = user_endpoint.is_admin(username)
    lms_client.close()

    # Serialize session cookies for later use
    serialized = serialize_session(auth.session)

    session["logged_in"] = True
    session["username"] = username
    session["is_admin"] = is_admin
    session["umu_session"] = serialized

    return jsonify({"success": True, "is_admin": is_admin})


@app.route("/api/logout", methods=["POST"])
def api_logout() -> Response:
    """Clear session and log out."""
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/status")
def api_auth_status() -> Response:
    """Return current authentication status."""
    return jsonify({
        "logged_in": session.get("logged_in", False),
        "username": session.get("username"),
        "is_admin": session.get("is_admin", False),
    })


@app.route("/api/sync/users/start", methods=["POST"])
def api_sync_users_start() -> Response:
    """Start user sync."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    serialized = session.get("umu_session")
    if not serialized:
        return jsonify({"success": False, "error": "会话已过期"}), 401

    sync_service.start_sync_users(serialized)
    return jsonify({"success": True})


@app.route("/api/sync/users/status")
def api_sync_users_status() -> Response:
    """SSE stream for user sync progress."""
    def generate():
        import time

        last_state = None
        while True:
            status = sync_service.user_status
            state = {
                "running": status.running,
                "progress": status.progress,
                "total": status.total,
                "message": status.message,
                "error": status.error,
                "completed": status.completed,
            }
            if state != last_state:
                yield f"data: {json.dumps(state)}\n\n"
                last_state = state.copy()
            if not status.running and (status.completed or status.error):
                yield f"data: {json.dumps(state)}\n\n"
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/sync/courses/start", methods=["POST"])
def api_sync_courses_start() -> Response:
    """Start course sync."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    serialized = session.get("umu_session")
    if not serialized:
        return jsonify({"success": False, "error": "会话已过期"}), 401

    data = request.get_json(silent=True) or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    sync_service.start_sync_courses(serialized, start_date=start_date, end_date=end_date)
    return jsonify({"success": True})


@app.route("/api/sync/courses/status")
def api_sync_courses_status() -> Response:
    """SSE stream for course sync progress."""
    def generate():
        import time

        last_state = None
        while True:
            status = sync_service.course_status
            state = {
                "running": status.running,
                "progress": status.progress,
                "total": status.total,
                "message": status.message,
                "error": status.error,
                "completed": status.completed,
            }
            if state != last_state:
                yield f"data: {json.dumps(state)}\n\n"
                last_state = state.copy()
            if not status.running and (status.completed or status.error):
                yield f"data: {json.dumps(state)}\n\n"
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/governance/preview")
def api_governance_preview() -> Response:
    """Return preview stats for a date range."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    data = governance_service.preview_governance(start_date=start_date, end_date=end_date)
    return jsonify({"success": True, **data})


@app.route("/api/governance/start", methods=["POST"])
def api_governance_start() -> Response:
    """Start governance audit."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    serialized = session.get("umu_session")
    if not serialized:
        return jsonify({"success": False, "error": "会话已过期"}), 401

    data = request.get_json(silent=True) or {}
    run_id = governance_service.start_governance(
        serialized,
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    return jsonify({"success": True, "run_id": run_id})


@app.route("/api/governance/status")
def api_governance_status() -> Response:
    """SSE stream for governance progress."""
    def generate():
        import time

        last_state = None
        while True:
            status = governance_service.status
            state = {
                "running": status.running,
                "progress": status.progress,
                "total": status.total,
                "message": status.message,
                "error": status.error,
                "completed": status.completed,
                "run_id": status.run_id,
                "current_course": status.current_course,
                "compliant_count": status.compliant_count,
                "non_compliant_count": status.non_compliant_count,
                "major_count": status.major_count,
                "current_course_level": status.current_course_level,
                "current_course_issues": status.current_course_issues,
            }
            if state != last_state:
                yield f"data: {json.dumps(state)}\n\n"
                last_state = state.copy()
            if not status.running and (status.completed or status.error):
                yield f"data: {json.dumps(state)}\n\n"
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/governance/runs")
def api_governance_runs() -> Response:
    """Return all governance runs."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    runs = governance_service.get_runs()
    return jsonify({"success": True, "runs": runs})


@app.route("/api/governance/current")
def api_governance_current() -> Response:
    """Return the currently active governance run (non-SSE)."""
    if not session.get("logged_in"):
        return jsonify({"running": False}), 401
    if not session.get("is_admin"):
        return jsonify({"running": False}), 403

    status = governance_service.status
    return jsonify({
        "running": status.running,
        "run_id": status.run_id,
        "progress": status.progress,
        "total": status.total,
        "message": status.message,
    })


@app.route("/api/governance/runs/<run_id>", methods=["DELETE"])
def api_governance_delete_run(run_id: str) -> Response:
    """Delete a single governance run."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    deleted = governance_service.delete_run(run_id)
    if not deleted:
        return jsonify({"success": False, "error": "运行记录不存在"}), 404
    return jsonify({"success": True})


@app.route("/api/governance/runs", methods=["DELETE"])
def api_governance_clear_runs() -> Response:
    """Delete all governance runs."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    count = governance_service.clear_all_runs()
    return jsonify({"success": True, "count": count})


@app.route("/api/governance/runs/<run_id>/results")
def api_governance_results(run_id: str) -> Response:
    """Return results for a governance run."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    data = governance_service.get_results(run_id)
    return jsonify({"success": True, **data})


@app.route("/api/governance/runs/<run_id>/export")
def api_governance_export(run_id: str) -> Response:
    """Export governance results for a run as Excel."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    data = governance_service.get_results(run_id)
    if not data.get("run"):
        return jsonify({"success": False, "error": "运行记录不存在"}), 404

    results = data.get("results", [])
    if not results:
        return jsonify({"success": False, "error": "没有可导出的结果"}), 404

    level_map = {
        "ok": "合规",
        "major": "需治理",
        "minor": "需治理",
        "unknown": "需治理",
    }

    rule_names = [
        "课程名称",
        "课程形式",
        "内容分类",
        "课程介绍",
        "课程学时",
        "课程评价/考试",
        "必修小节",
        "课程课件",
    ]

    rows: list[dict[str, Any]] = []
    for r in results:
        row: dict[str, Any] = {
            "课程ID": r.get("course_id", ""),
            "课程名称": r.get("course_name", ""),
            "创建者": r.get("creator_name", ""),
            "创建者邮箱": r.get("creator_email", ""),
            "UMU链接": r.get("umu_link", ""),
            "合规状态": "合规" if r.get("overall_compliant") else "不合规",
            "治理等级": level_map.get(r.get("overall_level", ""), "需治理"),
            "不合规原因": "; ".join(r.get("issues", [])),
        }
        rule_results = r.get("rule_results", [])
        for idx, name in enumerate(rule_names, start=1):
            rule = rule_results[idx - 1] if idx <= len(rule_results) else {}
            row[f"规则{idx}_{name}"] = level_map.get(rule.get("level", ""), "")
            row[f"规则{idx}_详情"] = rule.get("issue", "")
        rows.append(row)

    df = pd.DataFrame(rows)
    timestamp = now_beijing().strftime("%Y%m%d_%H%M%S")
    filename = f"governance_{run_id}_{timestamp}.xlsx"

    buffer = io.BytesIO()
    df.to_excel(buffer, sheet_name="治理结果", index=False)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# ------------------------------------------------------------------
# Governance Config APIs
# ------------------------------------------------------------------


@app.route("/api/governance/config", methods=["GET"])
def api_governance_config_get() -> Response:
    """Return all governance rule configurations."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    config_service = GovernanceConfigService()
    configs = config_service.get_all_configs()
    return jsonify({"success": True, "configs": configs})


@app.route("/api/governance/config", methods=["POST"])
def api_governance_config_post() -> Response:
    """Update governance configuration(s)."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    data = request.get_json(silent=True) or {}
    config_service = GovernanceConfigService()

    # Batch update: {configs: [{key, value}]}
    configs = data.get("configs")
    if isinstance(configs, list):
        for item in configs:
            key = item.get("key")
            value = item.get("value")
            if key is not None:
                config_service.set_config(key, value)
        return jsonify({"success": True})

    # Single update: {key, value}
    key = data.get("key")
    value = data.get("value")
    if key is None:
        return jsonify({"success": False, "error": "缺少key参数"}), 400

    config_service.set_config(key, value)
    return jsonify({"success": True})


@app.route("/api/governance/config/reset", methods=["POST"])
def api_governance_config_reset() -> Response:
    """Reset all governance configs to defaults."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    config_service = GovernanceConfigService()
    config_service.reset_to_defaults()
    return jsonify({"success": True})


@app.route("/api/governance/runs/<run_id>/resume", methods=["POST"])
def api_governance_resume(run_id: str) -> Response:
    """Resume an interrupted governance run."""
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "未登录"}), 401
    if not session.get("is_admin"):
        return jsonify({"success": False, "error": "需要管理员权限"}), 403

    serialized = session.get("umu_session")
    if not serialized:
        return jsonify({"success": False, "error": "会话已过期"}), 401

    started = governance_service.resume_governance(run_id, serialized)
    if not started:
        return jsonify({"success": False, "error": "无法继续该运行记录（可能正在运行或状态不允许）"}), 400

    return jsonify({"success": True, "run_id": run_id})
