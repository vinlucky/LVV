import sqlite3
import uuid
import json
from datetime import datetime, timezone
from .config import DB_PATH

_conn = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_tables()
    return _conn


def _init_tables():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            conv_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL DEFAULT 'chat',
            title TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '',
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (conv_id) REFERENCES conversations(conv_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_format TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            conv_id TEXT,
            mode TEXT DEFAULT 'chat',
            is_generated INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (conv_id) REFERENCES conversations(conv_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'pending',
            input_data TEXT DEFAULT '',
            output_data TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conv_id);
        CREATE INDEX IF NOT EXISTS idx_files_conv_id ON files(conv_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_task_type ON conversations(task_type);
        CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
    """)

    try:
        conn.execute("ALTER TABLE messages ADD COLUMN metadata TEXT DEFAULT ''")
    except Exception:
        pass


def create_conversation(task_type: str = "chat", title: str = "") -> dict:
    conn = get_conn()
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO conversations (conv_id, task_type, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, task_type, title, now, now),
    )
    conn.commit()
    return {"conv_id": conv_id, "task_type": task_type, "title": title, "created_at": now, "updated_at": now}


def get_conversation(conv_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM conversations WHERE conv_id = ?", (conv_id,)).fetchone()
    if not row:
        return None
    conv = dict(row)
    msgs = conn.execute(
        "SELECT role, content, timestamp FROM messages WHERE conv_id = ? ORDER BY id ASC", (conv_id,)
    ).fetchall()
    conv["messages"] = [dict(m) for m in msgs]
    return conv


def list_conversations(limit: int = 50, offset: int = 0, task_type: str | None = None) -> list[dict]:
    conn = get_conn()
    if task_type:
        rows = conn.execute(
            """SELECT c.* FROM conversations c
               INNER JOIN messages m ON c.conv_id = m.conv_id
               WHERE c.task_type = ?
               GROUP BY c.conv_id
               ORDER BY c.updated_at DESC LIMIT ? OFFSET ?""",
            (task_type, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT c.* FROM conversations c
               INNER JOIN messages m ON c.conv_id = m.conv_id
               GROUP BY c.conv_id
               ORDER BY c.updated_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(conv_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
    conn.commit()


def add_message(conv_id: str, role: str, content: str, metadata: str = "") -> dict:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO messages (conv_id, role, content, metadata, timestamp) VALUES (?, ?, ?, ?, ?)",
        (conv_id, role, content, metadata, now),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE conv_id = ?",
        (now, conv_id),
    )
    conn.commit()
    return {"conv_id": conv_id, "role": role, "content": content, "metadata": metadata, "timestamp": now}


MODE_TITLE_PREFIX = {
    "chat": "通用",
    "general": "通用",
    "meeting": "会议",
    "literature": "摘要",
    "polish": "润色",
    "ppt": "PPT",
}


def update_conversation_title(conv_id: str, title: str, mode: str = ""):
    conn = get_conn()
    prefix = MODE_TITLE_PREFIX.get(mode, "")
    if prefix and not title.startswith(prefix):
        title = f"{prefix} - {title}"
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE conv_id = ?",
        (title, datetime.now(timezone.utc).isoformat(), conv_id),
    )
    conn.commit()


def search_conversations(keyword: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT c.* FROM conversations c
        LEFT JOIN messages m ON c.conv_id = m.conv_id
        WHERE c.title LIKE ? OR m.content LIKE ?
        ORDER BY c.updated_at DESC LIMIT ?
        """,
        (f"%{keyword}%", f"%{keyword}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_conversations_by_type() -> dict:
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.* FROM conversations c
           INNER JOIN messages m ON c.conv_id = m.conv_id
           GROUP BY c.conv_id
           ORDER BY c.updated_at DESC"""
    ).fetchall()
    grouped = {}
    for c in rows:
        r = dict(c)
        t = r.get("task_type", "chat")
        if t not in grouped:
            grouped[t] = []
        grouped[t].append(r)
    return {"groups": grouped}


def save_file_record(filename: str, stored_filename: str, file_path: str, file_format: str = "",
                     file_size: int = 0, conv_id: str | None = None, mode: str = "chat",
                     is_generated: bool = False) -> dict:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO files (filename, stored_filename, file_path, file_format, file_size, conv_id, mode, is_generated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (filename, stored_filename, file_path, file_format, file_size, conv_id, mode, 1 if is_generated else 0, now),
    )
    conn.commit()
    record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {
        "id": record_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "file_path": file_path,
        "file_format": file_format,
        "file_size": file_size,
        "conv_id": conv_id,
        "mode": mode,
        "is_generated": is_generated,
        "created_at": now,
    }


def get_files_by_conv(conv_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM files WHERE conv_id = ? ORDER BY created_at DESC", (conv_id,)
    ).fetchall()
    from pathlib import Path
    from .config import FILE_DIR
    result = []
    for r in rows:
        d = dict(r)
        fp = Path(d["file_path"]) if d.get("file_path") else None
        if fp and fp.exists():
            try:
                d["relative_path"] = str(fp.relative_to(FILE_DIR.parent)).replace("\\", "/")
            except ValueError:
                d["relative_path"] = ""
        else:
            d["relative_path"] = d.get("relative_path", "")
        if d["relative_path"]:
            d["download_url"] = f"/files/download/{d['relative_path']}"
        else:
            d["download_url"] = d.get("download_url", "")
        result.append(d)
    return result


def get_all_files(mode: str | None = None) -> list[dict]:
    conn = get_conn()
    if mode:
        rows = conn.execute(
            "SELECT * FROM files WHERE mode = ? ORDER BY created_at DESC", (mode,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM files ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_file_conv_id(filename: str, conv_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM files WHERE stored_filename = ? OR filename = ?", (filename, filename)
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE files SET conv_id = ? WHERE id = ?", (conv_id, row["id"])
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM files WHERE id = ?", (row["id"],)).fetchone())


def create_task(task_type: str, input_data: str = "") -> dict:
    conn = get_conn()
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO tasks (task_id, task_type, status, input_data, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?, ?)",
        (task_id, task_type, input_data, now, now),
    )
    conn.commit()
    return {"task_id": task_id, "task_type": task_type, "status": "pending", "created_at": now}


def update_task(task_id: str, status: str | None = None, output_data: str | None = None) -> dict | None:
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    if status and output_data is not None:
        conn.execute(
            "UPDATE tasks SET status = ?, output_data = ?, updated_at = ? WHERE task_id = ?",
            (status, output_data, now, task_id),
        )
    elif status:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (status, now, task_id),
        )
    elif output_data is not None:
        conn.execute(
            "UPDATE tasks SET output_data = ?, updated_at = ? WHERE task_id = ?",
            (output_data, now, task_id),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def get_task(task_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(status: str | None = None) -> list[dict]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def record_token_usage(provider: str, model: str, prompt_tokens: int = 0,
                       completion_tokens: int = 0, total_tokens: int = 0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO token_usage (provider, model, prompt_tokens, completion_tokens, total_tokens) VALUES (?, ?, ?, ?, ?)",
        (provider, model, prompt_tokens, completion_tokens, total_tokens),
    )
    conn.commit()


def get_token_usage_stats() -> dict:
    conn = get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(total_tokens), 0) as total FROM token_usage WHERE date(created_at) = ?",
        (today,),
    ).fetchone()
    daily_usage = row["total"]
    budget = 1000000
    remaining = max(0, budget - daily_usage)
    return {"daily_usage": daily_usage, "budget": budget, "remaining": remaining}