from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS styles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    examples TEXT NOT NULL DEFAULT '',
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_text TEXT NOT NULL DEFAULT '',
                    ocr_text TEXT NOT NULL DEFAULT '',
                    response_text TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    style_id INTEGER,
                    topic TEXT NOT NULL DEFAULT '',
                    signals_json TEXT NOT NULL DEFAULT '{}',
                    extracted_json TEXT NOT NULL DEFAULT '{}',
                    generation_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ocr_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT NOT NULL DEFAULT '',
                    raw_text TEXT NOT NULL DEFAULT '',
                    corrected_text TEXT NOT NULL DEFAULT '',
                    engine TEXT NOT NULL DEFAULT '',
                    verdict TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS response_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_text TEXT NOT NULL DEFAULT '',
                    ocr_text TEXT NOT NULL DEFAULT '',
                    raw_response TEXT NOT NULL DEFAULT '',
                    corrected_response TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    style_id INTEGER,
                    verdict TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column(db, "conversations", "topic", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(db, "conversations", "signals_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(db, "conversations", "extracted_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(db, "conversations", "generation_ms", "INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = [row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        with self.connect() as db:
            cursor = db.execute(query, params)
            return int(cursor.lastrowid)

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as db:
            return list(db.execute(query, params).fetchall())

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute(query, params).fetchone()

    @staticmethod
    def encode_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    @staticmethod
    def decode_json(value: str) -> dict[str, Any]:
        try:
            payload = json.loads(value)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
