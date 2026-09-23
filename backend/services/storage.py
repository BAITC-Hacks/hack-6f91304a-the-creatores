import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from backend.errors import AppError
from backend.models import Model


class Storage:
    """Immutable datasets/calculations; conversation writes protected by a SQLite lease."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "state.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY(kind, id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS leases (
                id TEXT PRIMARY KEY, expires REAL NOT NULL)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, kind: str, record_id: UUID, value: Model):
        with self.connect() as db:
            db.execute(
                "INSERT INTO records VALUES (?, ?, ?)",
                (kind, str(record_id), value.model_dump_json()),
            )

    def get(self, kind: str, record_id: UUID, model):
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM records WHERE kind=? AND id=?", (kind, str(record_id))
            ).fetchone()
        if row is None:
            raise AppError(404, "not_found", "Набор данных, расчёт или беседа не найдены.")
        return model.model_validate_json(row[0])

    def save_conversation(self, conversation):
        with self.connect() as db:
            db.execute(
                "UPDATE records SET body=? WHERE kind='conversation' AND id=?",
                (conversation.model_dump_json(), str(conversation.conversation_id)),
            )

    @contextmanager
    def conversation_lease(self, conversation_id: UUID, seconds: float):
        key = str(conversation_id)
        with self.connect() as db:
            db.execute("DELETE FROM leases WHERE expires < ?", (time.time(),))
            try:
                db.execute("INSERT INTO leases VALUES (?, ?)", (key, time.time() + seconds))
            except sqlite3.IntegrityError as exc:
                raise AppError(
                    409,
                    "conversation_busy",
                    "Дождитесь ответа на предыдущее сообщение этой беседы.",
                ) from exc
        try:
            yield
        finally:
            with self.connect() as db:
                db.execute("DELETE FROM leases WHERE id=?", (key,))
