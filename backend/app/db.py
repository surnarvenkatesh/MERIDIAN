"""Lightweight SQLite persistence — no ORM overhead, just what the app needs:
research sessions (for history + audit) and feedback (for reward shaping)."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager

from .config import settings
from .models import ResearchResult

_DB_PATH = settings.database_url.replace("sqlite:///", "")


def _ensure_dir() -> None:
    d = os.path.dirname(_DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)


@contextmanager
def _conn():
    _ensure_dir()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                confidence REAL NOT NULL,
                total_reward REAL NOT NULL,
                elapsed_ms INTEGER NOT NULL,
                num_sources INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                custom_title TEXT,
                pinned INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Additive migration for databases created before these columns existed.
        existing_cols = {row["name"] for row in c.execute("PRAGMA table_info(sessions)").fetchall()}
        if "custom_title" not in existing_cols:
            c.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT")
        if "pinned" not in existing_cols:
            c.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        if "share_token" not in existing_cols:
            c.execute("ALTER TABLE sessions ADD COLUMN share_token TEXT")
        if "user_id" not in existing_cols:
            c.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                rating TEXT NOT NULL,
                comment TEXT,
                created_at REAL NOT NULL
            )
            """
        )


def save_session(result: ResearchResult, user_id: int | None = None) -> None:
    with _conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO sessions
               (id, query, answer, confidence, total_reward, elapsed_ms, num_sources, result_json, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.session_id,
                result.query,
                result.answer,
                result.confidence,
                result.total_reward,
                result.elapsed_ms,
                len(result.sources),
                result.model_dump_json(),
                time.time(),
                user_id,
            ),
        )


def list_sessions(limit: int = 30, user_id: int | None = None) -> list[dict]:
    with _conn() as c:
        if user_id is not None:
            rows = c.execute(
                "SELECT id, query, answer, confidence, total_reward, elapsed_ms, num_sources, "
                "created_at, custom_title, pinned "
                "FROM sessions WHERE user_id = ? ORDER BY pinned DESC, created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, query, answer, confidence, total_reward, elapsed_ms, num_sources, "
                "created_at, custom_title, pinned "
                "FROM sessions ORDER BY pinned DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def rename_session(session_id: str, title: str) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET custom_title = ? WHERE id = ?", (title, session_id))


def set_session_pinned(session_id: str, pinned: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET pinned = ? WHERE id = ?", (1 if pinned else 0, session_id))


def get_or_create_share_token(session_id: str) -> str | None:
    import uuid
    with _conn() as c:
        row = c.execute("SELECT share_token FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        if row["share_token"]:
            return row["share_token"]
        token = uuid.uuid4().hex
        c.execute("UPDATE sessions SET share_token = ? WHERE id = ?", (token, session_id))
        return token


def get_session_by_share_token(token: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT result_json FROM sessions WHERE share_token = ?", (token,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def revoke_share_token(session_id: str) -> None:
    with _conn() as c:
        c.execute("UPDATE sessions SET share_token = NULL WHERE id = ?", (session_id,))


def delete_session(session_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        c.execute("DELETE FROM feedback WHERE session_id = ?", (session_id,))


def get_session(session_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT result_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def create_user(email: str, password_hash: str) -> int | None:
    with _conn() as c:
        try:
            cursor = c.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email.lower().strip(), password_hash, time.time()),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # email already registered


def get_user_by_email(email: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_password_hash_by_id(user_id: int) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["password_hash"] if row else None


def update_password(user_id: int, new_password_hash: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))


def save_feedback(session_id: str, rating: str, comment: str | None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback (session_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (session_id, rating, comment, time.time()),
        )
