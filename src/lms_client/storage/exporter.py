"""Data export utilities (CSV, Excel, JSON)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class DataExporter:
    """Export database tables to various file formats."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_to_csv(
        self,
        table_name: str,
        filepath: str | Path,
        **filters: Any,
    ) -> Path:
        """Export filtered records to CSV."""
        records = self.db.query(table_name, **filters)
        df = pd.DataFrame(records)
        output = Path(filepath)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False, encoding="utf-8-sig")
        logger.info("Exported %d rows to %s", len(df), output)
        return output

    def export_to_excel(
        self,
        table_name: str,
        filepath: str | Path,
        sheet_name: str | None = None,
        **filters: Any,
    ) -> Path:
        """Export filtered records to Excel."""
        records = self.db.query(table_name, **filters)
        df = pd.DataFrame(records)
        output = Path(filepath)
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet = sheet_name or table_name
        df.to_excel(output, sheet_name=sheet, index=False)
        logger.info("Exported %d rows to %s", len(df), output)
        return output

    def export_to_json(
        self,
        table_name: str,
        filepath: str | Path,
        **filters: Any,
    ) -> Path:
        """Export filtered records to JSON."""
        records = self.db.query(table_name, **filters)
        output = Path(filepath)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, cls=_DateTimeEncoder)
        logger.info("Exported %d rows to %s", len(records), output)
        return output

    def export_all(
        self,
        output_dir: str | Path,
        fmt: str = "xlsx",
    ) -> list[Path]:
        """Export all known tables to the specified format."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exported: list[Path] = []

        known_tables = ["users", "organizations", "courses", "sessions", "student_tasks"]
        for table_name in known_tables:
            stats = self.db.get_stats(table_name)
            if not stats.get("exists") or stats.get("count", 0) == 0:
                continue

            if fmt == "csv":
                path = output_dir / f"{table_name}.csv"
                self.export_to_csv(table_name, path)
            elif fmt in ("xlsx", "excel"):
                path = output_dir / f"{table_name}.xlsx"
                self.export_to_excel(table_name, path)
            elif fmt == "json":
                path = output_dir / f"{table_name}.json"
                self.export_to_json(table_name, path)
            else:
                raise ValueError(f"Unsupported format: {fmt}")
            exported.append(path)

        return exported
