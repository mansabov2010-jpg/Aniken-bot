import sqlite3
from typing import Optional, List, Dict, Any

DB_PATH = "aniken_bot.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                chat_type TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_ref TEXT UNIQUE,
                title TEXT,
                url TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                category TEXT,
                title TEXT,
                poster_file_id TEXT,
                episodes TEXT,
                genre TEXT,
                year TEXT,
                language TEXT,
                quality TEXT,
                storage_channel TEXT,
                storage_msg_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def add_user(user_id: int, full_name: str, username: Optional[str]) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, full_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username
        """, (user_id, full_name, username or ""))
        conn.commit()


def add_chat(chat_id: int, title: str, chat_type: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO chats (chat_id, title, chat_type)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                chat_type = excluded.chat_type
        """, (chat_id, title, chat_type))
        conn.commit()


def get_stats() -> Dict[str, int]:
    with get_conn() as conn:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        chats_count = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        contents_count = conn.execute("SELECT COUNT(*) FROM contents").fetchone()[0]
        req_count = conn.execute("SELECT COUNT(*) FROM required_channels").fetchone()[0]
    return {
        "users": users_count,
        "chats": chats_count,
        "contents": contents_count,
        "req_channels": req_count,
    }


def get_all_user_ids() -> List[int]:
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]


def get_all_chat_ids() -> List[int]:
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT chat_id FROM chats").fetchall()]


def list_required_channels() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM required_channels ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def add_required_channel(channel_ref: str, title: str, url: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO required_channels (channel_ref, title, url)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_ref) DO UPDATE SET title = excluded.title, url = excluded.url
        """, (channel_ref, title, url))
        conn.commit()


def remove_required_channel(channel_ref: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM required_channels WHERE channel_ref = ?", (channel_ref,))
        conn.commit()


def save_content(data: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO contents (
                code, category, title, poster_file_id, episodes,
                genre, year, language, quality, storage_channel, storage_msg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                category = excluded.category,
                title = excluded.title,
                poster_file_id = excluded.poster_file_id,
                episodes = excluded.episodes,
                genre = excluded.genre,
                year = excluded.year,
                language = excluded.language,
                quality = excluded.quality,
                storage_channel = excluded.storage_channel,
                storage_msg_id = excluded.storage_msg_id
        """, (
            data["code"],
            data["category"],
            data["title"],
            data["poster_file_id"],
            data["episodes"],
            data["genre"],
            data["year"],
            data["language"],
            data["quality"],
            data["storage_channel"],
            data["storage_msg_id"],
        ))
        conn.commit()


def get_content_by_code(code: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM contents WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def search_contents(query: str) -> List[Dict[str, Any]]:
    q = f"%{query.strip()}%"
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM contents
            WHERE code = ? OR LOWER(title) LIKE LOWER(?) OR LOWER(genre) LIKE LOWER(?)
            ORDER BY id DESC LIMIT 15
        """, (query.strip(), q, q)).fetchall()
        return [dict(r) for r in rows]


def list_contents(category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM contents WHERE category = ? ORDER BY id DESC LIMIT ?",
                (category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM contents ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
