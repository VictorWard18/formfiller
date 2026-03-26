"""
PostgreSQL database for storing company data dictionaries persistently.
Works with Digital Ocean's managed dev database (free tier).
Falls back to SQLite for local development.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _use_postgres():
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


# ─── PostgreSQL ──────────────────────────────────────────────

def _pg_connect():
    import psycopg2
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = False
    return conn


def _pg_init():
    conn = _pg_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dictionaries (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'ru',
            data TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fill_history (
            id SERIAL PRIMARY KEY,
            dictionary_id INTEGER NOT NULL REFERENCES dictionaries(id),
            form_filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _pg_create(name, language, data):
    conn = _pg_connect()
    cur = conn.cursor()
    now = datetime.utcnow()
    cur.execute(
        "INSERT INTO dictionaries (name, language, data, created_at, updated_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (name, language, json.dumps(data, ensure_ascii=False), now, now),
    )
    dict_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return dict_id


def _pg_get(dict_id):
    conn = _pg_connect()
    cur = conn.cursor()
    cur.execute("SELECT id, name, language, data, created_at, updated_at FROM dictionaries WHERE id = %s", (dict_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "language": row[2],
        "data": json.loads(row[3]),
        "created_at": row[4].isoformat() if row[4] else None,
        "updated_at": row[5].isoformat() if row[5] else None,
    }


def _pg_list():
    conn = _pg_connect()
    cur = conn.cursor()
    cur.execute("SELECT id, name, language, created_at, updated_at FROM dictionaries ORDER BY updated_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "language": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "updated_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


def _pg_update(dict_id, data):
    conn = _pg_connect()
    cur = conn.cursor()
    now = datetime.utcnow()
    cur.execute(
        "UPDATE dictionaries SET data = %s, updated_at = %s WHERE id = %s",
        (json.dumps(data, ensure_ascii=False), now, dict_id),
    )
    updated = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return updated


def _pg_delete(dict_id):
    conn = _pg_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM fill_history WHERE dictionary_id = %s", (dict_id,))
    cur.execute("DELETE FROM dictionaries WHERE id = %s", (dict_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted


# ─── SQLite (local dev fallback) ─────────────────────────────

SQLITE_PATH = os.environ.get("DB_PATH", "/tmp/formfiller/formfiller.db")


def _sq_connect():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _sq_init():
    conn = _sq_connect()
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


def _sq_create(name, language, data):
    conn = _sq_connect()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO dictionaries (name, language, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, language, json.dumps(data, ensure_ascii=False), now, now),
    )
    conn.commit()
    dict_id = cur.lastrowid
    conn.close()
    return dict_id


def _sq_get(dict_id):
    conn = _sq_connect()
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


def _sq_list():
    conn = _sq_connect()
    rows = conn.execute(
        "SELECT id, name, language, created_at, updated_at FROM dictionaries ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _sq_update(dict_id, data):
    conn = _sq_connect()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "UPDATE dictionaries SET data = ?, updated_at = ? WHERE id = ?",
        (json.dumps(data, ensure_ascii=False), now, dict_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def _sq_delete(dict_id):
    conn = _sq_connect()
    conn.execute("DELETE FROM fill_history WHERE dictionary_id = ?", (dict_id,))
    conn.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))
    conn.commit()
    conn.close()
    return True


# ─── Public API (auto-selects backend) ───────────────────────

def init_db():
    if _use_postgres():
        _pg_init()
        print("Using PostgreSQL database")
    else:
        _sq_init()
        print("Using SQLite (local dev mode)")


def create_dictionary(name: str, language: str, data: dict) -> int:
    if _use_postgres():
        return _pg_create(name, language, data)
    return _sq_create(name, language, data)


def get_dictionary(dict_id: int) -> Optional[dict]:
    if _use_postgres():
        return _pg_get(dict_id)
    return _sq_get(dict_id)


def list_dictionaries() -> list[dict]:
    if _use_postgres():
        return _pg_list()
    return _sq_list()


def update_dictionary(dict_id: int, data: dict) -> bool:
    if _use_postgres():
        return _pg_update(dict_id, data)
    return _sq_update(dict_id, data)


def delete_dictionary(dict_id: int) -> bool:
    if _use_postgres():
        return _pg_delete(dict_id)
    return _sq_delete(dict_id)
