from __future__ import annotations

from app.storage.database import Database


class AnalyticsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def total_generated(self) -> int:
        row = self.database.fetch_one("SELECT COUNT(*) AS count FROM conversations")
        return int(row["count"]) if row else 0

    def average_generation_ms(self) -> int:
        row = self.database.fetch_one(
            """
            SELECT AVG(NULLIF(generation_ms, 0)) AS value
            FROM conversations
            """
        )
        value = row["value"] if row else None
        return int(value or 0)

    def slowest_generation_ms(self) -> int:
        row = self.database.fetch_one("SELECT MAX(generation_ms) AS value FROM conversations")
        value = row["value"] if row else None
        return int(value or 0)

    def ocr_feedback_totals(self) -> dict[str, int]:
        row = self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN verdict = 'correct' THEN 1 ELSE 0 END) AS correct_count,
                SUM(CASE WHEN verdict = 'corrected' THEN 1 ELSE 0 END) AS corrected_count
            FROM ocr_feedback
            """
        )
        if not row:
            return {"total": 0, "correct_count": 0, "corrected_count": 0}
        return {
            "total": int(row["total"] or 0),
            "correct_count": int(row["correct_count"] or 0),
            "corrected_count": int(row["corrected_count"] or 0),
        }

    def response_feedback_totals(self) -> dict[str, int]:
        row = self.database.fetch_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN verdict = 'correct' THEN 1 ELSE 0 END) AS correct_count,
                SUM(CASE WHEN verdict = 'corrected' THEN 1 ELSE 0 END) AS corrected_count
            FROM response_feedback
            """
        )
        if not row:
            return {"total": 0, "correct_count": 0, "corrected_count": 0}
        return {
            "total": int(row["total"] or 0),
            "correct_count": int(row["correct_count"] or 0),
            "corrected_count": int(row["corrected_count"] or 0),
        }

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
