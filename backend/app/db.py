"""
Persistence layer supporting both SQLite (local development, zero setup)
and Postgres (production, e.g. Neon) automatically based on DATABASE_URL.

Local dev: DATABASE_URL=sqlite:///./data/agent.db (the default)
Production: DATABASE_URL=postgresql://user:pass@host/dbname

The two dialects differ in a handful of specific ways (placeholders,
upsert syntax, auto-increment, column-existence checks, last-insert-id) -
each is handled explicitly below rather than hidden behind an ORM, so the
SQL stays readable and auditable.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager

from .config import settings
from .models import ResearchResult

IS_POSTGRES = settings.database_url.startswith(("postgres://", "postgresql://"))
_DB_PATH = settings.database_url.replace("sqlite:///", "")

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


def _q(sql: str) -> str:
    """Translate SQLite's '?' placeholders to Postgres's '%s' when needed."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


def _ensure_dir() -> None:
    if IS_POSTGRES:
        return
    d = os.path.dirname(_DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)


@contextmanager
def _conn():
    if IS_POSTGRES:
        conn = psycopg.connect(settings.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        _ensure_dir()
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _column_exists(c, table: str, column: str) -> bool:
    if IS_POSTGRES:
        row = c.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, column),
        ).fetchone()
        return row is not None
    cols = {row["name"] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def init_db() -> None:
    with _conn() as c:
        if IS_POSTGRES:
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
                    created_at DOUBLE PRECISION NOT NULL,
                    custom_title TEXT,
                    pinned INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        else:
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

        if not _column_exists(c, "sessions", "custom_title"):
            c.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT")
        if not _column_exists(c, "sessions", "pinned"):
            c.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(c, "sessions", "share_token"):
            c.execute("ALTER TABLE sessions ADD COLUMN share_token TEXT")
        if not _column_exists(c, "sessions", "user_id"):
            c.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")

        if IS_POSTGRES:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    comment TEXT,
                    created_at DOUBLE PRECISION NOT NULL
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS rl_policy_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    payload TEXT NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                )
                """
            )
        else:
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
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS rl_policy_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )


def save_session(result: ResearchResult, user_id: int | None = None) -> None:
    with _conn() as c:
        if IS_POSTGRES:
            c.execute(
                _q(
                    """INSERT INTO sessions
                       (id, query, answer, confidence, total_reward, elapsed_ms, num_sources, result_json, created_at, user_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (id) DO UPDATE SET
                           query = EXCLUDED.query, answer = EXCLUDED.answer, confidence = EXCLUDED.confidence,
                           total_reward = EXCLUDED.total_reward, elapsed_ms = EXCLUDED.elapsed_ms,
                           num_sources = EXCLUDED.num_sources, result_json = EXCLUDED.result_json,
                           created_at = EXCLUDED.created_at, user_id = EXCLUDED.user_id"""
                ),
                (
                    result.session_id, result.query, result.answer, result.confidence, result.total_reward,
                    result.elapsed_ms, len(result.sources), result.model_dump_json(), time.time(), user_id,
                ),
            )
        else:
            c.execute(
                """INSERT OR REPLACE INTO sessions
                   (id, query, answer, confidence, total_reward, elapsed_ms, num_sources, result_json, created_at, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.session_id, result.query, result.answer, result.confidence, result.total_reward,
                    result.elapsed_ms, len(result.sources), result.model_dump_json(), time.time(), user_id,
                ),
            )


def list_sessions(limit: int = 30, user_id: int | None = None) -> list[dict]:
    with _conn() as c:
        if user_id is not None:
            rows = c.execute(
                _q(
                    "SELECT id, query, answer, confidence, total_reward, elapsed_ms, num_sources, "
                    "created_at, custom_title, pinned "
                    "FROM sessions WHERE user_id = ? ORDER BY pinned DESC, created_at DESC LIMIT ?"
                ),
                (user_id, limit),
            ).fetchall()
        else:
            rows = c.execute(
                _q(
                    "SELECT id, query, answer, confidence, total_reward, elapsed_ms, num_sources, "
                    "created_at, custom_title, pinned "
                    "FROM sessions ORDER BY pinned DESC, created_at DESC LIMIT ?"
                ),
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def rename_session(session_id: str, title: str) -> None:
    with _conn() as c:
        c.execute(_q("UPDATE sessions SET custom_title = ? WHERE id = ?"), (title, session_id))


def set_session_pinned(session_id: str, pinned: bool) -> None:
    with _conn() as c:
        c.execute(_q("UPDATE sessions SET pinned = ? WHERE id = ?"), (1 if pinned else 0, session_id))


def get_session_owner(session_id: str) -> int | None:
    with _conn() as c:
        row = c.execute(_q("SELECT user_id FROM sessions WHERE id = ?"), (session_id,)).fetchone()
        return row["user_id"] if row else None


def get_or_create_share_token(session_id: str) -> str | None:
    import uuid
    with _conn() as c:
        row = c.execute(_q("SELECT share_token FROM sessions WHERE id = ?"), (session_id,)).fetchone()
        if row is None:
            return None
        if row["share_token"]:
            return row["share_token"]
        token = uuid.uuid4().hex
        c.execute(_q("UPDATE sessions SET share_token = ? WHERE id = ?"), (token, session_id))
        return token


def get_session_by_share_token(token: str) -> dict | None:
    with _conn() as c:
        row = c.execute(_q("SELECT result_json FROM sessions WHERE share_token = ?"), (token,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def revoke_share_token(session_id: str) -> None:
    with _conn() as c:
        c.execute(_q("UPDATE sessions SET share_token = NULL WHERE id = ?"), (session_id,))


def delete_session(session_id: str) -> None:
    with _conn() as c:
        c.execute(_q("DELETE FROM sessions WHERE id = ?"), (session_id,))
        c.execute(_q("DELETE FROM feedback WHERE session_id = ?"), (session_id,))


def get_session(session_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(_q("SELECT result_json FROM sessions WHERE id = ?"), (session_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def create_user(email: str, password_hash: str) -> int | None:
    with _conn() as c:
        try:
            if IS_POSTGRES:
                row = c.execute(
                    _q("INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?) RETURNING id"),
                    (email.lower().strip(), password_hash, time.time()),
                ).fetchone()
                return row["id"]
            else:
                cursor = c.execute(
                    "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                    (email.lower().strip(), password_hash, time.time()),
                )
                return cursor.lastrowid
        except (sqlite3.IntegrityError, Exception) as exc:
            if IS_POSTGRES and "UniqueViolation" not in type(exc).__name__:
                raise
            return None


def get_user_by_email(email: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            _q("SELECT id, email, password_hash FROM users WHERE email = ?"), (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute(_q("SELECT id, email FROM users WHERE id = ?"), (user_id,)).fetchone()
        return dict(row) if row else None


def get_password_hash_by_id(user_id: int) -> str | None:
    with _conn() as c:
        row = c.execute(_q("SELECT password_hash FROM users WHERE id = ?"), (user_id,)).fetchone()
        return row["password_hash"] if row else None


def update_password(user_id: int, new_password_hash: str) -> None:
    with _conn() as c:
        c.execute(_q("UPDATE users SET password_hash = ? WHERE id = ?"), (new_password_hash, user_id))


def save_feedback(session_id: str, rating: str, comment: str | None) -> None:
    with _conn() as c:
        c.execute(
            _q("INSERT INTO feedback (session_id, rating, comment, created_at) VALUES (?, ?, ?, ?)"),
            (session_id, rating, comment, time.time()),
        )


def load_rl_policy_state() -> dict | None:
    """Loads the persisted RL policy (weights, baseline, reward history) from
    the database, so it survives restarts/redeploys instead of resetting -
    a local JSON file would be wiped on every Render free-tier restart."""
    with _conn() as c:
        row = c.execute(_q("SELECT payload FROM rl_policy_state WHERE id = 1")).fetchone()
        return json.loads(row["payload"]) if row else None


def save_rl_policy_state(payload: dict) -> None:
    with _conn() as c:
        if IS_POSTGRES:
            c.execute(
                _q(
                    "INSERT INTO rl_policy_state (id, payload, updated_at) VALUES (1, ?, ?) "
                    "ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at"
                ),
                (json.dumps(payload), time.time()),
            )
        else:
            c.execute(
                "INSERT OR REPLACE INTO rl_policy_state (id, payload, updated_at) VALUES (1, ?, ?)",
                (json.dumps(payload), time.time()),
            )
