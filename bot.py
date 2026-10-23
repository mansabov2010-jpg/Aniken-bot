"""Bot sozlamalari. Hamma narsa muhit o'zgaruvchilaridan (Environment Variables) olinadi."""
import hashlib
import os
import re
 
try:  # lokal ishga tushirishda .env faylini o'qiydi (Render'da kerak emas)
    from dotenv import load_dotenv
 
    load_dotenv()
except ImportError:  # pragma: no cover
    pass
 
BOT_TOKEN = os.getenv("BOT_TOKEN", "8987164421:AAHIKjTCtB4781Ns53b3WSHk5xgAWOXTtQ8").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
 
# Animening "Kanal:" qatorida chiqadigan standart kanal
DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL", "@AniMax_uzb").strip()
 
# Adminlar Telegram ID'lari (vergul yoki probel bilan ajratiladi): 123456789,987654321
ADMIN_IDS = {int(x) for x in re.findall(r"-?\d+", os.getenv("ADMIN_IDS", "7986354170,7637155944"))}
 
# Render avtomatik RENDER_EXTERNAL_URL beradi. Bo'lsa webhook, bo'lmasa polling.
BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or ""
).strip().rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or hashlib.sha256(
    BOT_TOKEN.encode()
).hexdigest()[:48]
 
# Render bepul tarifida uxlab qolmasligi uchun o'z-o'ziga so'rov yuborib turadi
KEEPALIVE = os.getenv("KEEPALIVE", "1") == "1"
"""Barcha matnlar shu yerda."""
from html import escape
 
 
def anime_caption(a: dict) -> str:
    """Anime kartochkasi: kanal postidagi ko'rinishning aynan o'zi."""
    return (
        f"{escape(a['title'])}\n"
        "<blockquote>"
        f"├▸ Qism: {escape(a['episode'])}\n"
        f"├▸ Holati: {escape(a['status'])}\n"
        f"├▸ Sifat - {escape(a['quality'])}\n"
        f"├▸ Janrlari: {escape(a['genres'])}\n"
        f"├▸ Kanal: {escape(a['channel'])}"
        "</blockquote>"
    )
 
 
WATCH_BUTTON = "✨TOMOSHA QILISH✨"
 
WELCOME = (
    "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
    "🎌 <b>Anime botiga xush kelibsiz!</b>\n"
    "Bu yerda sevimli animelaringizni o'zbek tilida topib, tomosha qilishingiz mumkin.\n\n"
    "Quyidagi bo'limlardan birini tanlang 👇"
)
MENU_TEXT = "🏠 <b>Bosh menyu</b>\n\nKerakli bo'limni tanlang 👇"
HELP_TEXT = (
    "ℹ️ <b>Yordam</b>\n\n"
    "🔍 <b>Anime qidirish</b> — anime nomi yoki kodi bilan izlang.\n"
    "🔥 <b>Eng mashhur animelar</b> — eng ko'p ko'rilganlar.\n"
    "🆕 <b>Yangi animelar</b> — oxirgi qo'shilganlar.\n"
    "📜 <b>Barcha animelar</b> — to'liq ro'yxat.\n\n"
    "Anime kartochkasidagi <b>✨TOMOSHA QILISH✨</b> tugmasini bossangiz, "
    "anime joylangan kanalga o'tasiz."
)
SEARCH_NAME_TEXT = (
    "🔍 <b>Anime qidirish</b>\n\n"
    "Anime <b>nomini</b> yozing.\n"
    "Masalan: <code>Moviy quti</code>"
)
SEARCH_CODE_TEXT = (
    "🔢 <b>Kod orqali qidirish</b>\n\n"
    "Anime <b>kodini</b> yozing.\n"
    "Masalan: <code>125</code>"
)
NOT_FOUND = (
    "😕 <b>Hech narsa topilmadi.</b>\n\n"
    "Nomini boshqacha yozib ko'ring yoki kod orqali izlang."
)
SUB_TEXT = (
    "📢 <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
    "A'zo bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing."
)
NO_ANIME = "📭 Hozircha animelar qo'shilmagan."
 
ADMIN_WELCOME = (
    "👨‍💻 <b>Admin panel</b>\n\n"
    "Xush kelibsiz! Kerakli bo'limni tanlang 👇"
)
ADMIN_EDIT_MENU = (
    "✏️ <b>Animelarni tahrirlash</b>\n\n"
    "Bo'limni tanlang 👇"
)
ADMIN_CH_MENU = (
    "📢 <b>Majburiy a'zolik</b>\n\n"
    "Foydalanuvchilar botdan foydalanishi uchun a'zo bo'lishi shart bo'lgan kanallar."
)
 
PROMPTS = {
    "poster": "📸 Anime <b>rasmini</b> (posterini) yuboring.",
    "title": "🎬 Anime <b>nomini</b> yozing.\nMasalan: <code>Moviy quti</code>",
    "episode": "🎞 <b>Qism</b>ni yozing.\nMasalan: <code>2-fasl 3-qism</code>",
    "status": "📡 <b>Holati</b>ni tanlang yoki yozing.\nMasalan: <code>Davom etmoqda</code>",
    "quality": "🖥 <b>Sifat</b>ni yozing.\nMasalan: <code>720p, 1080p</code>",
    "genres": "🎭 <b>Janrlari</b>ni yozing (vergul bilan).\nMasalan: <code>Maktab, Romantika</code>",
    "channel": (
        "📢 Kartochkadagi <b>Kanal</b> nomini yozing (@username).\n"
        "Masalan: <code>@AniMax_uzb</code>"
    ),
    "link": (
        "🔗 Anime joylangan <b>kanal (guruh) havolasi</b>ni yuboring.\n"
        "Masalan: <code>https://t.me/kanal_nomi</code> yoki <code>https://t.me/+AbCdEf...</code>\n\n"
        "<i>Foydalanuvchi ✨TOMOSHA QILISH✨ tugmasini bossa, shu havolaga o'tadi.</i>"
    ),
    "code": (
        "🔢 Anime <b>kodi</b>ni yozing.\n"
        "Foydalanuvchilar shu kod orqali animeni topadi. Har bir kod noyob bo'lishi kerak."
    ),
}

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
 
import config
 
 
class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in config.ADMIN_IDS)
"""PostgreSQL (asyncpg) bilan ishlash."""
import logging
from typing import Optional
 
import asyncpg
 
log = logging.getLogger(__name__)
 
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          BIGINT PRIMARY KEY,
    full_name   TEXT,
    username    TEXT,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT now()
);
 
CREATE TABLE IF NOT EXISTS animes (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL,
    title       TEXT NOT NULL,
    episode     TEXT NOT NULL,
    status      TEXT NOT NULL,
    quality     TEXT NOT NULL,
    genres      TEXT NOT NULL,
    channel     TEXT NOT NULL,
    link        TEXT NOT NULL,
    poster      TEXT NOT NULL,
    views       INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS animes_code_idx ON animes (lower(code));
 
CREATE TABLE IF NOT EXISTS channels (
    id       SERIAL PRIMARY KEY,
    chat_id  BIGINT NOT NULL UNIQUE,
    title    TEXT NOT NULL,
    link     TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""
 
ANIME_FIELDS = (
    "code", "title", "episode", "status", "quality",
    "genres", "channel", "link", "poster",
)
 
 
def _like(q: str) -> str:
    q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{q}%"
 
 
class Database:
    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None
 
    async def connect(self, dsn: str) -> None:
        self.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        async with self.pool.acquire() as c:
            await c.execute(SCHEMA)
        log.info("Ma'lumotlar bazasiga ulandi")
 
    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
 
    # ---------------- foydalanuvchilar ----------------
    async def touch_user(self, uid: int, full_name: str, username: Optional[str]) -> None:
        await self.pool.execute(
            """INSERT INTO users (id, full_name, username) VALUES ($1,$2,$3)
               ON CONFLICT (id) DO UPDATE
               SET full_name=$2, username=$3, active=TRUE, last_active=now()""",
            uid, full_name, username,
        )
 
    async def user_ids(self) -> list[int]:
        rows = await self.pool.fetch("SELECT id FROM users WHERE active")
        return [r["id"] for r in rows]
 
    async def set_inactive(self, uid: int) -> None:
        await self.pool.execute("UPDATE users SET active=FALSE WHERE id=$1", uid)
 
    async def stats(self) -> dict:
        r = await self.pool.fetchrow(
            """SELECT
                (SELECT count(*) FROM users) AS users,
                (SELECT count(*) FROM users WHERE active) AS active,
                (SELECT count(*) FROM users WHERE joined_at > now() - interval '1 day') AS new_today,
                (SELECT count(*) FROM users WHERE last_active > now() - interval '1 day') AS online_today,
                (SELECT count(*) FROM animes) AS animes,
                (SELECT coalesce(sum(views),0) FROM animes) AS views,
                (SELECT count(*) FROM channels) AS channels"""
        )
        return dict(r)
 
    # ---------------- animelar ----------------
    async def add_anime(self, d: dict) -> int:
        return await self.pool.fetchval(
            """INSERT INTO animes (code,title,episode,status,quality,genres,channel,link,poster)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id""",
            *(d[f] for f in ANIME_FIELDS),
        )
 
    async def update_anime(self, aid: int, d: dict) -> None:
        sets = ", ".join(f"{f}=${i}" for i, f in enumerate(ANIME_FIELDS, start=2))
        await self.pool.execute(
            f"UPDATE animes SET {sets} WHERE id=$1", aid, *(d[f] for f in ANIME_FIELDS)
        )
 
    async def delete_anime(self, aid: int) -> None:
        await self.pool.execute("DELETE FROM animes WHERE id=$1", aid)
 
    async def get_anime(self, aid: int) -> Optional[dict]:
        r = await self.pool.fetchrow("SELECT * FROM animes WHERE id=$1", aid)
        return dict(r) if r else None
 
    async def by_code(self, code: str) -> Optional[dict]:
        r = await self.pool.fetchrow(
            "SELECT * FROM animes WHERE lower(code)=lower($1)", code.strip()
        )
        return dict(r) if r else None
 
    async def code_exists(self, code: str, exclude_id: Optional[int] = None) -> bool:
        r = await self.pool.fetchval(
            "SELECT id FROM animes WHERE lower(code)=lower($1) AND id IS DISTINCT FROM $2",
            code.strip(), exclude_id,
        )
        return r is not None
 
    async def search_title(self, q: str, limit: int = 20) -> list[dict]:
        rows = await self.pool.fetch(
            r"SELECT * FROM animes WHERE title ILIKE $1 ESCAPE '\' ORDER BY views DESC, id DESC LIMIT $2",
            _like(q.strip()), limit,
        )
        return [dict(r) for r in rows]
 
    async def top(self, limit: int = 10) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT * FROM animes ORDER BY views DESC, id DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]
 
    async def newest(self, limit: int = 10) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT * FROM animes ORDER BY id DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]
 
    async def page(self, page: int, per: int = 10) -> tuple[list[dict], int]:
        total = await self.pool.fetchval("SELECT count(*) FROM animes")
        rows = await self.pool.fetch(
            "SELECT * FROM animes ORDER BY title ASC LIMIT $1 OFFSET $2", per, page * per
        )
        return [dict(r) for r in rows], total
 
    async def add_view(self, aid: int) -> None:
        await self.pool.execute("UPDATE animes SET views=views+1 WHERE id=$1", aid)
 
    # ---------------- majburiy kanallar ----------------
    async def add_channel(self, chat_id: int, title: str, link: Optional[str]) -> bool:
        r = await self.pool.execute(
            """INSERT INTO channels (chat_id,title,link) VALUES ($1,$2,$3)
               ON CONFLICT (chat_id) DO NOTHING""",
            chat_id, title, link,
        )
        return r.endswith("1")
 
    async def channels(self) -> list[dict]:
        rows = await self.pool.fetch("SELECT * FROM channels ORDER BY id")
        return [dict(r) for r in rows]
 
    async def get_channel(self, cid: int) -> Optional[dict]:
        r = await self.pool.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        return dict(r) if r else None
 
    async def delete_channel(self, cid: int) -> None:
        await self.pool.execute("DELETE FROM channels WHERE id=$1", cid)
 
 
db = Database()
"""Yordamchi funksiyalar: havolalar, kanal tekshirish, obuna tekshirish."""
import logging
import re
from typing import Optional, Union
 
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
 
log = logging.getLogger(__name__)
 
_TME = re.compile(r"^(?:https?://)?(?:t|telegram)\.me/(.+)$", re.I)
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
 
 
def normalize_link(text: str) -> Optional[str]:
    """Foydalanuvchi yozgan havolani to'g'ri https://t.me/... ko'rinishiga keltiradi."""
    t = (text or "").strip()
    if t.startswith("@") and _USERNAME.match(t[1:]):
        return f"https://t.me/{t[1:]}"
    m = _TME.match(t)
    if m and m.group(1).strip("/"):
        return "https://t.me/" + m.group(1).strip("/")
    return None
 
 
def parse_chat_ref(text: str) -> Union[int, str, None]:
    """Ochiq kanal (@username, t.me/username) yoki raqamli ID ni ajratadi.
    Maxfiy havola (t.me/+...) uchun None qaytaradi."""
    t = (text or "").strip()
    if re.fullmatch(r"-?\d{5,}", t):
        return int(t)
    if t.startswith("@") and _USERNAME.match(t[1:]):
        return t
    m = _TME.match(t)
    if m:
        part = m.group(1).split("/")[0].split("?")[0]
        if part and not part.startswith("+") and part.lower() != "joinchat" and _USERNAME.match(part):
            return "@" + part
    return None
 
 
async def bot_is_admin(bot: Bot, chat_id: Union[int, str]) -> bool:
    me = await bot.me()
    m = await bot.get_chat_member(chat_id, me.id)
    return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
 
 
async def check_link(bot: Bot, link: str) -> str:
    """Anime kanali havolasi tekshiriladi. Natija — 'ulanganlik' belgisi bilan matn."""
    ref = parse_chat_ref(link)
    if ref is None:
        return "⚠️ Maxfiy havola — avtomatik tekshirib bo'lmadi (havola saqlanadi)"
    try:
        chat = await bot.get_chat(ref)
    except TelegramAPIError:
        return "❌ Kanal topilmadi (havolani tekshiring)"
    try:
        if await bot_is_admin(bot, chat.id):
            return f"✅ Kanal ulangan: {chat.title}"
    except TelegramAPIError:
        pass
    return f"⚠️ Kanal topildi ({chat.title}), lekin bot u yerda admin emas"
 
 
async def is_member(bot: Bot, chat_id: int, user_id: int) -> Optional[bool]:
    """True/False — a'zomi. None — tekshirib bo'lmadi (masalan, bot kanaldan chiqarilgan)."""
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError as e:
        log.warning("A'zolikni tekshirib bo'lmadi (chat=%s): %s", chat_id, e)
        return None
    if m.status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    ):
        return True
    if m.status == ChatMemberStatus.RESTRICTED:
        return bool(m.is_member)
    return False
 
 
async def missing_channels(bot: Bot, channels: list[dict], user_id: int) -> list[dict]:
    """Foydalanuvchi a'zo bo'lmagan majburiy kanallar ro'yxati."""
    out = []
    for ch in channels:
        if await is_member(bot, ch["chat_id"], user_id) is False:
            out.append(ch)
    return out
 from aiogram.fsm.state import State, StatesGroup
 
 
class Search(StatesGroup):
    name = State()
    code = State()
 
 
class Flow(StatesGroup):
    """Anime joylash / tahrirlash qadamlari."""
    step = State()
    confirm = State()
 
 
class Find(StatesGroup):
    """Admin: tahrirlash yoki o'chirish uchun animeni qidirish."""
    edit = State()
    delete = State()
 
 
class Channel(StatesGroup):
    add = State()
 
 
class Broadcast(StatesGroup):
    wait = State()
    confirm = State()
 
