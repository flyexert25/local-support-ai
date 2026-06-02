"""SQLAlchemy data layer for Local Support AI.

This package is intentionally added beside the existing sqlite3 storage layer.
Current app flows can keep using `app.storage.database.Database` while new
backend features gradually move to explicit ORM models and repositories.
"""

