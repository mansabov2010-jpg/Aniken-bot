import os
import sqlite3
from typing import Any

DB_PATH = os.getenv("DB_PATH", "bot_data.db")


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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                chat_type TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                code TEXT PRIMARY KEY,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                channel_ref TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extra_admins (
                user_id INTEGER PRIMARY KEY,
                label TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def add_user(user_id: int, full_name: str | None, username: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, full_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username
            """,
            (user_id, full_name or "", username or ""),
        )
        conn.commit()


def find_user_by_username(username: str) -> dict[str, Any] | None:
    clean_u = username.lstrip("@").strip().lower()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, full_name, username FROM users WHERE LOWER(username) = ?",
            (clean_u,),
        ).fetchone()
        return dict(row) if row else None


def get_all_user_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [int(r["user_id"]) for r in rows]


def add_chat(chat_id: int, title: str, chat_type: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO chats (chat_id, title, chat_type)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                chat_type = excluded.chat_type
            """,
            (chat_id, title, chat_type),
        )
        conn.commit()


def get_all_chat_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT chat_id FROM chats").fetchall()
        return [int(r["chat_id"]) for r in rows]


def add_extra_admin(user_id: int, label: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO extra_admins (user_id, label)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                label = CASE WHEN excluded.label != '' THEN excluded.label ELSE extra_admins.label END
            """,
            (user_id, label),
        )
        conn.commit()


def remove_extra_admin(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM extra_admins WHERE user_id = ?", (user_id,))
        conn.commit()


def list_extra_admins() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, label, added_at FROM extra_admins ORDER BY rowid ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def save_content(data: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO contents (
                code, category, title, poster_file_id, episodes, genre,
                year, language, quality, storage_channel, storage_msg_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            """,
            (
                str(data["code"]).strip(),
                data.get("category", "anime"),
                data.get("title", ""),
                data.get("poster_file_id", ""),
                data.get("episodes", ""),
                data.get("genre", ""),
                data.get("year", ""),
                data.get("language", ""),
                data.get("quality", ""),
                str(data.get("storage_channel", "")),
                int(data.get("storage_msg_id", 0)),
            ),
        )
        conn.commit()


def get_content_by_code(code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM contents WHERE LOWER(code) = LOWER(?)",
            (code.strip(),),
        ).fetchone()
        return dict(row) if row else None


def search_contents(query: str) -> list[dict[str, Any]]:
    q = f"%{query.strip()}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contents WHERE LOWER(title) LIKE LOWER(?) OR LOWER(code) LIKE LOWER(?) LIMIT 20",
            (q, q),
        ).fetchall()
        return [dict(r) for r in rows]


def list_contents(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contents ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def count_contents_by_category() -> dict[str, int]:
    """Har bir bo'limdagi (kino / multfilm / anime) kontentlar soni."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS c FROM contents GROUP BY category"
        ).fetchall()
        return {str(r["category"]): int(r["c"]) for r in rows}


def list_contents_by_category(category: str, limit: int = 8, offset: int = 0) -> list[dict[str, Any]]:
    """Bo'lim bo'yicha kontentlar (yangilari birinchi), sahifalash bilan."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contents WHERE category = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
            (category, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_content(code: str) -> bool:
    """Kontentni bazadan o'chiradi. O'chirilgan bo'lsa True qaytaradi."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM contents WHERE LOWER(code) = LOWER(?)",
            (code.strip(),),
        )
        conn.commit()
        return cur.rowcount > 0


def add_required_channel(channel_ref: str, title: str, url: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO required_channels (channel_ref, title, url)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_ref) DO UPDATE SET
                title = excluded.title,
                url = excluded.url
            """,
            (channel_ref.strip(), title.strip(), url.strip()),
        )
        conn.commit()


def remove_required_channel(channel_ref: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM required_channels WHERE channel_ref = ?", (channel_ref,))
        conn.commit()


def list_required_channels() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT channel_ref, title, url FROM required_channels").fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict[str, int]:
    with get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        chats = conn.execute("SELECT COUNT(*) AS c FROM chats").fetchone()["c"]
        contents = conn.execute("SELECT COUNT(*) AS c FROM contents").fetchone()["c"]
        req_channels = conn.execute("SELECT COUNT(*) AS c FROM required_channels").fetchone()["c"]
        extra_adm = conn.execute("SELECT COUNT(*) AS c FROM extra_admins").fetchone()["c"]
        return {
            "users": int(users),
            "chats": int(chats),
            "contents": int(contents),
            "req_channels": int(req_channels),
            "extra_admins": int(extra_adm),
        }
