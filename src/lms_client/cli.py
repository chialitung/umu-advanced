"""Command-line interface for the LMS client SDK."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .auth import SessionAuth, TokenAuth
from .client import LMSClient
from .storage.database import DatabaseManager
from .storage.exporter import DataExporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def cmd_login(args: argparse.Namespace) -> int:
    """Authenticate and save session state."""
    auth: TokenAuth | SessionAuth
    if args.username and args.password:
        auth = TokenAuth(
            username=args.username,
            password=args.password,
            login_url=f"{args.url}/passport/ajax/account/login",
        )
    else:
        auth = SessionAuth()

    with LMSClient(base_url=args.url, auth=auth) as client:
        # A simple probe to validate auth
        try:
            result = client.get("/uapi/v1/enterprise/info")
            print("Login successful")
            if result:
                print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
        except Exception as exc:
            print(f"Login failed: {exc}", file=sys.stderr)
            return 1

    return 0


def cmd_list_users(args: argparse.Namespace) -> int:
    """List users and optionally save to file."""
    auth = SessionAuth()
    with LMSClient(base_url=args.url, auth=auth) as client:
        users = client.get("/uapi/v1/enterprise/user-list", params={"size": args.limit})

    if not users:
        print("No users found")
        return 0

    if args.output:
        output_path = Path(args.output)
        if output_path.suffix == ".json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        elif output_path.suffix in (".xlsx", ".xls"):
            import pandas as pd
            pd.DataFrame(users).to_excel(output_path, index=False)
        else:
            import pandas as pd
            pd.DataFrame(users).to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"Saved to {output_path}")
    else:
        print(json.dumps(users, ensure_ascii=False, indent=2))

    return 0


def cmd_export_all(args: argparse.Namespace) -> int:
    """Export all known tables from the local database."""
    db = DatabaseManager(database_url=args.db)
    exporter = DataExporter(db)

    if not Path(args.output_dir).exists():
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    exported = exporter.export_all(args.output_dir, fmt=args.format)
    print(f"Exported {len(exported)} files to {args.output_dir}")
    for path in exported:
        print(f"  - {path}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync API data into local database."""
    db = DatabaseManager(database_url=args.db)
    db.create_tables()

    auth = SessionAuth()
    with LMSClient(base_url=args.url, auth=auth) as client:
        # Example: sync users
        try:
            users = client.get("/uapi/v1/enterprise/user-list", params={"size": 1000})
            if isinstance(users, list):
                db.save("users", users)
                print(f"Synced {len(users)} users")
            elif isinstance(users, dict) and "data" in users:
                db.save("users", users["data"])
                print(f"Synced {len(users['data'])} users")
        except Exception as exc:
            logger.warning("User sync failed: %s", exc)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lms-cli", description="UMU LMS CLI")
    parser.add_argument("--url", default="https://www.umu.cn", help="Base API URL")
    sub = parser.add_subparsers(dest="command", required=True)

    login_p = sub.add_parser("login", help="Authenticate with the LMS")
    login_p.add_argument("--username", help="Account username")
    login_p.add_argument("--password", help="Account password")

    list_p = sub.add_parser("list-users", help="List enterprise users")
    list_p.add_argument("--limit", type=int, default=100, help="Max users to fetch")
    list_p.add_argument("--output", help="Output file (.csv, .xlsx, .json)")

    export_p = sub.add_parser("export-all", help="Export all local DB tables")
    export_p.add_argument("--output-dir", default="./exports", help="Output directory")
    export_p.add_argument("--format", default="xlsx", choices=["csv", "xlsx", "json"])
    export_p.add_argument("--db", default="sqlite:///lms.db", help="Database URL")

    sync_p = sub.add_parser("sync", help="Sync API data to local database")
    sync_p.add_argument("--db", default="sqlite:///lms.db", help="Database URL")

    args = parser.parse_args(argv)

    if args.command == "login":
        return cmd_login(args)
    if args.command == "list-users":
        return cmd_list_users(args)
    if args.command == "export-all":
        return cmd_export_all(args)
    if args.command == "sync":
        return cmd_sync(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
