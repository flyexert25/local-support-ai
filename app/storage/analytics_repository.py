from __future__ import annotations

from app.storage.database import Database


class AnalyticsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def total_generated(self) -> int:
        row = self.database.fetch_one("SELECT COUNT(*) AS count FROM conversations")
        return int(row["count"]) if row else 0

    def top_topics(self, limit: int = 8) -> list[tuple[str, int]]:
        rows = self.database.fetch_all(
            """
            SELECT COALESCE(NULLIF(topic, ''), 'Без темы') AS topic, COUNT(*) AS count
            FROM conversations
            GROUP BY COALESCE(NULLIF(topic, ''), 'Без темы')
            ORDER BY count DESC, topic ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [(str(row["topic"]), int(row["count"])) for row in rows]

    def recent_cases(self, limit: int = 5) -> list[dict[str, str]]:
        rows = self.database.fetch_all(
            """
            SELECT topic, signals_json, extracted_json, created_at
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            {
                "topic": str(row["topic"] or "Без темы"),
                "signals_json": str(row["signals_json"] or "{}"),
                "extracted_json": str(row["extracted_json"] or "{}"),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
