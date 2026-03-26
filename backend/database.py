"""
SQLite database for storing company data dictionaries.
Each dictionary is a named collection of key-value fields extracted from PDFs.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "/tmp/formfiller/formfiller.db")


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dictionaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'ru',
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fill_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dictionary_id INTEGER NOT NULL,
            form_filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (dictionary_id) REFERENCES dictionaries(id)
        );
    """)
    conn.commit()
    conn.close()


def create_dictionary(name: str, language: str, data: dict) -> int:
    conn = get_db()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO dictionaries (name, language, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, language, json.dumps(data, ensure_ascii=False), now, now),
    )
    conn.commit()
    dict_id = cursor.lastrowid
    conn.close()
    return dict_id


def get_dictionary(dict_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM dictionaries WHERE id = ?", (dict_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "language": row["language"],
        "data": json.loads(row["data"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_dictionaries() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, language, created_at, updated_at FROM dictionaries ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_dictionary(dict_id: int, data: dict) -> bool:
    conn = get_db()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "UPDATE dictionaries SET data = ?, updated_at = ? WHERE id = ?",
        (json.dumps(data, ensure_ascii=False), now, dict_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_dictionary(dict_id: int) -> bool:
    conn = get_db()
    cursor = conn.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
