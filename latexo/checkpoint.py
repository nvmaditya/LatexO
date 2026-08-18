from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _connect(store: Path) -> sqlite3.Connection:
    store.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(store)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT PRIMARY KEY,
            revision_id TEXT NOT NULL,
            patch_id TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    return conn


def save_checkpoints(store: Path, records: list[dict]) -> None:
    conn = _connect(store)
    try:
        conn.execute("BEGIN")
        for record in records:
            thread_id = record.get("thread_id")
            revision_id = record.get("revision_id")
            patch_id = record.get("patch_id")
            if not thread_id or not revision_id or not patch_id:
                raise ValueError("checkpoint requires thread_id, revision_id, patch_id")
            payload = json.dumps(record.get("payload") or {})
            conn.execute(
                """
                INSERT INTO checkpoints (thread_id, revision_id, patch_id, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    revision_id=excluded.revision_id,
                    patch_id=excluded.patch_id,
                    payload=excluded.payload
                """,
                (thread_id, revision_id, patch_id, payload),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_checkpoint(store: Path, thread_id: str) -> dict | None:
    if not store.exists():
        return None
    conn = _connect(store)
    try:
        row = conn.execute(
            "SELECT thread_id, revision_id, patch_id, payload FROM checkpoints WHERE thread_id=?",
            (thread_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "thread_id": row[0],
        "revision_id": row[1],
        "patch_id": row[2],
        "payload": json.loads(row[3]),
    }
