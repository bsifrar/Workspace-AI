from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List

from workspace_ai.app.settings import get_settings


class SessionStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_settings().storage_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, sort_keys=True)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'workspace',
                    external_conversation_id TEXT NOT NULL DEFAULT '',
                    external_title TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'chat',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'workspace',
                    state TEXT NOT NULL DEFAULT 'completed',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS api_calls (
                    call_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def create_session(self, *, project_id: str, title: str, mode: str, source: str = "workspace", external_conversation_id: str = "", external_title: str = "") -> Dict[str, Any]:
        session_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, project_id, title, source, external_conversation_id, external_title, mode, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (session_id, project_id, title or project_id, source, external_conversation_id, external_title, mode, now, now),
            )
            conn.commit()
        return self.get_session(session_id) or {}

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def update_session_status(self, *, session_id: str, status: str) -> Dict[str, Any] | None:
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?", (status, now, session_id))
            conn.commit()
        return self.get_session(session_id)

    def delete_session(self, *, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        return bool(row.rowcount)

    def list_sessions(self, *, project_id: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions"
        params: list[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(500, int(limit))))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def search_sessions(self, *, query: str, project_id: str | None = None, limit: int = 25) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions WHERE (title LIKE ? OR external_title LIKE ?)"
        needle = f"%{query.strip()}%"
        params: list[Any] = [needle, needle]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(200, int(limit))))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def list_imported_sessions(self, *, project_id: str | None = None, source: str = "chatgpt_export", limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions WHERE source = ?"
        params: list[Any] = [source]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(500, int(limit))))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def add_message(self, *, session_id: str, role: str, content: str, provider: str = "workspace", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        now = self._now_iso()
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(message_id, session_id, role, content, provider, state, metadata_json, created_at) VALUES(?, ?, ?, ?, ?, 'completed', ?, ?)",
                (message_id, session_id, role, content, provider, self._json(metadata), now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
            conn.commit()
        return self.get_message(message_id) or {}

    def get_message(self, message_id: str) -> Dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if not row:
            return None
        parsed = dict(row)
        parsed["metadata"] = json.loads(parsed.pop("metadata_json", "{}"))
        return parsed

    def list_messages(self, *, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, max(1, min(1000, int(limit)))),
            ).fetchall()
        payloads = []
        for row in rows:
            parsed = dict(row)
            parsed["metadata"] = json.loads(parsed.pop("metadata_json", "{}"))
            payloads.append(parsed)
        return payloads

    def create_checkpoint(self, *, session_id: str, summary: str, state: Dict[str, Any]) -> Dict[str, Any]:
        checkpoint_id = f"chk_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO checkpoints(checkpoint_id, session_id, summary, state_json, created_at) VALUES(?, ?, ?, ?, ?)",
                (checkpoint_id, session_id, summary, self._json(state), now),
            )
            conn.commit()
        return self.list_checkpoints(session_id=session_id, limit=1)[0]

    def list_checkpoints(self, *, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, max(1, min(500, int(limit)))),
            ).fetchall()
        out = []
        for row in rows:
            parsed = dict(row)
            parsed["state"] = json.loads(parsed.pop("state_json", "{}"))
            out.append(parsed)
        return out

    def set_setting(self, *, key: str, value: Any) -> None:
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value), now),
            )
            conn.commit()

    def list_settings(self) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings ORDER BY key ASC").fetchall()
        payload: Dict[str, Any] = {}
        for row in rows:
            payload[str(row["key"])] = json.loads(str(row["value"]))
        return payload

    def record_api_call(self, *, session_id: str, provider: str, model: str, mode: str, input_tokens: int, output_tokens: int, estimated_cost_usd: float) -> Dict[str, Any]:
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_calls(call_id, session_id, provider, model, mode, input_tokens, output_tokens, estimated_cost_usd, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (call_id, session_id, provider, model, mode, int(input_tokens), int(output_tokens), float(estimated_cost_usd), now),
            )
            conn.commit()
        return {"call_id": call_id, "created_at": now}

    def api_usage_summary(self) -> Dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(1) AS n, COALESCE(SUM(input_tokens), 0) AS in_tok, COALESCE(SUM(output_tokens), 0) AS out_tok, COALESCE(SUM(estimated_cost_usd), 0.0) AS cost FROM api_calls"
            ).fetchone()
            hour = conn.execute("SELECT COUNT(1) AS n FROM api_calls WHERE created_at >= datetime('now', '-1 hour')").fetchone()
            day = conn.execute("SELECT COUNT(1) AS n, COALESCE(SUM(estimated_cost_usd), 0.0) AS cost FROM api_calls WHERE substr(created_at,1,10)=substr(datetime('now'),1,10)").fetchone()
        return {
            "total_calls": int(total["n"] or 0),
            "total_input_tokens": int(total["in_tok"] or 0),
            "total_output_tokens": int(total["out_tok"] or 0),
            "total_estimated_cost_usd": float(total["cost"] or 0.0),
            "calls_this_hour": int(hour["n"] or 0),
            "calls_today": int(day["n"] or 0),
            "spent_today_usd": float(day["cost"] or 0.0),
        }
