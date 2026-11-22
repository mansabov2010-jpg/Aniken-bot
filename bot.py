import asyncio
import base64
import hashlib
import hmac
import html
import json
import os
import random
import re
import sqlite3
import tempfile
import time
import urllib.parse
from urllib.parse import parse_qsl
from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, WebAppInfo, ReactionTypeEmoji, FSInputFile, BufferedInputFile
)
import yt_dlp

import db


def clean_url(raw_url: str, fallback: str) -> str:
    if not raw_url:
        return fallback
    match = re.search(r"https?://[^\s\]\)\"'>]+", raw_url.strip())
    return match.group(0) if match else fallback


TG_TOKEN = os.getenv("TG_TOKEN", "").strip()
BASE_ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("TG_CHAT", "7986354170,7637155944").split(",")
    if x.strip().isdigit()
]
MAIN_CHANNEL = os.getenv("TG_CHANNEL", "@AniKinolar_kanal").strip()
OWNER_USER = os.getenv("OWNER_USER", "@Yegerist_mvp").strip()
BASE_MINIAPP_URL = clean_url(
    os.getenv("MINIAPP_URL", ""),
    "https://mansabov2010-jpg.github.io/Aniken-bot/miniapp/index.html"
)
# Mini ilova xabarlarni aynan shu manzilga yuboradi (bot o'zining Render manzili).
# Render RENDER_EXTERNAL_URL ni o'zi beradi, BACKEND_API_URL ni qo'lda ham berish mumkin.
BACKEND_API_URL = clean_url(
    os.getenv("BACKEND_API_URL", "") or os.getenv("RENDER_EXTERNAL_URL", ""),
    "",
)
PORT = int(os.getenv("PORT", "8080"))

EMOJI_WAVE = "👋"
EMOJI_FILM = "🎞"
EMOJI_BOT = "🤖"
URL_REGEX = re.compile(r"https?://\S+")

router = Router()
ACTIVE_BOT: Bot | None = None


# ════════════════════════════════════════════════════════════════
#  KELGAN XABARLAR (guruh / kanal / shaxsiy) → MINI ILOVA
# ════════════════════════════════════════════════════════════════

INBOX_DB = os.getenv("INBOX_DB", "inbox.db")
BG_TASKS: set = set()


def inbox_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(INBOX_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_inbox() -> None:
    conn = inbox_conn()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS inbox (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                msg_id INTEGER NOT NULL,
                sender TEXT,
                kind TEXT,
                text TEXT,
                reply_id INTEGER,
                reply_sender TEXT,
                reply_text TEXT,
                ts INTEGER NOT NULL
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def sender_name(m: Message) -> str:
    if m.from_user:
        return m.from_user.full_name
    if m.sender_chat:
        return m.sender_chat.title or str(m.sender_chat.id)
    return "Noma'lum"


def describe_message(m: Message) -> tuple[str, str]:
    """(turi, matn) qaytaradi. Stiker uchun matn = emoji."""
    if m.text:
        return "text", m.text
    if m.sticker:
        return "sticker", m.sticker.emoji or "🧸"
    cap = m.caption or ""
    labels = [
        (m.photo, "🖼 Rasm"),
        (m.video, "🎬 Video"),
        (m.voice, "🎙 Ovozli xabar"),
        (m.video_note, "⭕ Video xabar"),
        (m.audio, "🎵 Audio"),
        (m.animation, "🎞 GIF"),
        (m.document, "📎 Fayl"),
        (m.poll, "📊 So'rovnoma"),
        (m.location, "📍 Joylashuv"),
        (m.contact, "👤 Kontakt"),
    ]
    for obj, label in labels:
        if obj:
            return "media", label + (f": {cap}" if cap else "")
    if m.new_chat_members:
        return "media", "➕ Qo'shildi: " + ", ".join(u.full_name for u in m.new_chat_members)
    if m.left_chat_member:
        return "media", f"➖ Chiqib ketdi: {m.left_chat_member.full_name}"
    return "media", "📨 Xabar"


def record_incoming(m: Message) -> None:
    kind, text = describe_message(m)
    reply_id = reply_sender = reply_text = None
    r = m.reply_to_message
    if r:
        _, rtext = describe_message(r)
        reply_id = r.message_id
        reply_sender = sender_name(r)
        reply_text = (rtext or "")[:120]

    conn = inbox_conn()
    try:
        conn.execute(
            "INSERT INTO inbox (chat_id, msg_id, sender, kind, text, reply_id, reply_sender, reply_text, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(m.chat.id), m.message_id, sender_name(m), kind, text,
             reply_id, reply_sender, reply_text, int(time.time())),
        )
        conn.execute("DELETE FROM inbox WHERE seq <= (SELECT MAX(seq) FROM inbox) - 5000")
        conn.commit()
        print(f"[inbox] {m.chat.id} | {sender_name(m)}: {(text or '')[:40]}")
    finally:
        conn.close()


def fetch_inbox(since: int) -> tuple[list[dict], int, bool]:
    """(xabarlar, oxirgi_seq, reset) qaytaradi."""
    conn = inbox_conn()
    try:
        last_seq = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM inbox").fetchone()[0]
        reset = since > last_seq
        if since <= 0 or reset:
            rows = conn.execute(
                "SELECT * FROM (SELECT * FROM inbox ORDER BY seq DESC LIMIT 300) ORDER BY seq ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inbox WHERE seq > ? ORDER BY seq ASC LIMIT 500", (since,)
            ).fetchall()
    finally:
        conn.close()

    out: list[dict] = []
    for r in rows:
        is_sticker = r["kind"] == "sticker"
        out.append({
            "seq": r["seq"],
            "chat_id": r["chat_id"],
            "id": r["msg_id"],
            "sender": r["sender"],
            "type": "sticker" if is_sticker else "text",
            "text": "" if is_sticker else (r["text"] or ""),
            "sticker": (r["text"] or "🧸") if is_sticker else "",
            "replyTo": {
                "id": r["reply_id"],
                "sender": r["reply_sender"] or "Xabar",
                "text": r["reply_text"] or "",
            } if r["reply_id"] else None,
            "ts": r["ts"],
        })
    return out, last_seq, reset


class InboxMiddleware(BaseMiddleware):
    """Botga tushgan har bir xabarni (qaysi handler ishlashidan qat'i nazar) yozib qo'yadi."""

    async def __call__(self, handler, event, data):
        try:
            record_incoming(event)
            if event.chat.type == "private" and event.from_user:
                db.add_user(event.from_user.id, event.from_user.full_name, event.from_user.username)
        except Exception as e:
            print("inbox xatosi:", e)
        return await handler(event, data)


router.message.outer_middleware(InboxMiddleware())


@router.channel_post()
async def on_channel_post(message: Message):
    try:
        db.add_chat(message.chat.id, message.chat.title or str(message.chat.id), message.chat.type)
        record_incoming(message)
    except Exception as e:
        print("channel_post xatosi:", e)


# ════════════════════════════════════════════════════════════════
#  MINI ILOVADAN OMMAVIY XABAR TARQATISH
# ════════════════════════════════════════════════════════════════

async def _collect_broadcast_targets(bot: Bot, mode: str) -> list[int]:
    targets: list[int] = []
    if mode in ("users", "all"):
        targets.extend(db.get_all_user_ids())
    if mode in ("chats", "all"):
        targets.extend(db.get_all_chat_ids())
        if MAIN_CHANNEL.startswith("@"):
            try:
                ch = await bot.get_chat(MAIN_CHANNEL)
                targets.append(ch.id)
            except Exception:
                pass
    return list(dict.fromkeys(targets))


async def _broadcast_worker(bot: Bot, targets: list[int], text: str, admin_uid: int) -> None:
    sent = 0
    failed = 0
    body = fancy_text(text)
    for tid in targets:
        for attempt in range(2):
            try:
                await bot.send_message(chat_id=tid, text=body, parse_mode=ParseMode.HTML)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception:
                failed += 1
                break
        else:
            failed += 1
        await asyncio.sleep(0.05)
    try:
        await bot.send_message(
            chat_id=admin_uid,
            text=(
                "✅ <b>Mini ilovadan tarqatish yakunlandi!</b>\n"
                f"📤 Yuborildi: <b>{sent}</b>\n"
                f"⚠️ Xato / bloklangan: <b>{failed}</b>"
            ),
        )
    except Exception:
        pass


async def start_broadcast(bot: Bot, mode: str, text: str, admin_uid: int) -> tuple[bool, str]:
    text = (text or "").strip()
    if mode not in ("users", "chats", "all"):
        return False, "Tarqatish turi noto'g'ri"
    if not text:
        return False, "Xabar matni bo'sh"
    targets = await _collect_broadcast_targets(bot, mode)
    if not targets:
        return False, "Yuboriladigan manzil topilmadi"
    task = asyncio.create_task(_broadcast_worker(bot, targets, text, admin_uid))
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    return True, f"Tarqatish boshlandi: {len(targets)} manzil. Yakunida botdan hisobot keladi."


class AddContentFSM(StatesGroup):
    category = State()
    title = State()
    poster = State()
    episodes = State()
    genre = State()
    year = State()
    code = State()
    language = State()
    quality = State()
    storage_msg = State()


class EditContentFSM(StatesGroup):
    code = State()
    title = State()
    poster = State()
    episodes = State()
    genre = State()
    year = State()
    language = State()
    quality = State()


class BroadcastFSM(StatesGroup):
    mode = State()
    message = State()


class ReqChannelFSM(StatesGroup):
    channel_input = State()


class AddAdminFSM(StatesGroup):
    admin_input = State()


class DirectMsgFSM(StatesGroup):
    target_user = State()
    message_text = State()


def get_all_admin_ids() -> list[int]:
    ordered: list[int] = []
    for aid in BASE_ADMIN_IDS:
        if aid not in ordered:
            ordered.append(aid)
    for row in db.list_extra_admins():
        eid = int(row["user_id"])
        if eid not in ordered:
            ordered.append(eid)
    return ordered


def is_admin(user_id: int) -> bool:
    return user_id in get_all_admin_ids()


# Bot nomidan yuboriladigan matnlar uchun bezak (kerak bo'lmasa "" qiling)
STYLE_PREFIX = "✨ "


def fancy_text(text: str) -> str:
    """Matnni qalin + qiya (bold italic) qilib, oldiga bezak qo'shadi.
    Faqat emoji/belgidan iborat matn (stiker) o'zgarishsiz yuboriladi."""
    safe = html.escape(text or "", quote=False)
    if not any(ch.isalnum() for ch in safe):
        return safe
    return f"{STYLE_PREFIX}<b><i>{safe}</i></b>"


def parse_target_id(raw_target: str) -> int | str:
    s = str(raw_target or "").strip()
    if s.lstrip("-").isdigit():
        return int(s)
    return s


def make_chat_link(chat_id_str: str, username: str = "") -> str:
    s = (chat_id_str or "").strip()
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    if s.startswith("@"):
        return f"https://t.me/{s[1:]}"
    if s.startswith("-100") and s[4:].isdigit():
        return f"https://t.me/c/{s[4:]}"
    if s.isdigit():
        return f"https://t.me/user?id={s}"
    return f"https://t.me/{MAIN_CHANNEL.lstrip('@')}"


def _rows_as_dicts(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, tuple(r))) for r in cur.fetchall()]


def _pick(row: dict, *names: str, default: str = "") -> str:
    for n in names:
        if row.get(n) not in (None, ""):
            return str(row[n])
    return default


def load_lists() -> dict:
    """Bazadan guruh/kanal va kontaktlar ro'yxatini jonli o'qiydi."""
    groups: list[dict] = []
    contacts: list[dict] = []
    try:
        conn = db.get_conn()
        cur = conn.cursor()

        try:
            for r in _rows_as_dicts(cur, "SELECT * FROM chats"):
                cid = _pick(r, "chat_id", "id")
                if not cid:
                    continue
                title = _pick(r, "title", "name", default=cid)
                ctype = _pick(r, "chat_type", "type").lower()
                if "group" in ctype or "channel" in ctype or cid.startswith("-"):
                    groups.append({"id": cid, "name": title, "link": make_chat_link(cid)})
        except Exception as e:
            print("load_lists (chats) xatosi:", e)

        try:
            for r in _rows_as_dicts(cur, "SELECT * FROM users"):
                uid = _pick(r, "user_id", "id")
                if not uid:
                    continue
                fname = _pick(r, "full_name", "name", default=uid)
                uname = _pick(r, "username")
                contacts.append({"id": uid, "name": fname, "link": make_chat_link(uid, uname)})
        except Exception as e:
            print("load_lists (users) xatosi:", e)

        conn.close()
    except Exception as e:
        print("load_lists xatosi:", e)
    return {"groups": groups, "contacts": contacts}


def build_miniapp_url() -> str:
    payload = {**load_lists(), "api_base": BACKEND_API_URL, "incoming_message": None}

    encoded = urllib.parse.quote(json.dumps(payload, ensure_ascii=False))
    sep = "&" if "?" in BASE_MINIAPP_URL else "?"
    return f"{BASE_MINIAPP_URL}{sep}data={encoded}"


def format_welcome(full_name: str, bot_username: str, is_adm: bool) -> str:
    base = (
        f"{EMOJI_WAVE} Xush kelibsiz, <b>{full_name}</b>!\n\n"
        f"{EMOJI_FILM} <b>Havola, anime, multfilm yoki kino kodi / nomini yuboring</b>\n\n"
        f"{EMOJI_BOT} Ushbu bot <b>@{bot_username}</b> | Admin: <b>{OWNER_USER}</b>"
    )
    if is_adm:
        base += "\n\n🛡 <i>Admin huquqi faol. Barcha boshqaruv bo'limlari Admin Panel ichida.</i>"
    return base


def format_group_intro(chat_title: str, bot_username: str) -> str:
    main_ch_clean = MAIN_CHANNEL.lstrip("@")
    owner_clean = OWNER_USER.lstrip("@")
    return (
        f"✨ <b>Assalomu alaykum, «{chat_title}» jamoasi!</b> ✨\n\n"
        f"Men <b>@{bot_username}</b> botiman — har bir lahzani mazmunli va qulay qiladigan aqlli yordamchingiz.\n\n"
        f"🎬 <b>Nimalar qila olaman:</b>\n"
        f"• Havola yuborilganda videolarni o'zining asl ovozi bilan tez yuklab beraman;\n"
        f"• Anime, multfilm va kinolarni kod yoki nomi bo'yicha topib beraman;\n"
        f"• Guruh va foydalanuvchilar bilan tezkor aloqa va boshqaruvni ta'minlayman.\n\n"
        f"📌 <b>Asosiy ma'lumotlar:</b>\n"
        f"• <b>Owner (Yaratuvchi / Boshqaruvchi):</b> <a href=\"https://t.me/{owner_clean}\">{OWNER_USER}</a>\n"
        f"• <b>Asosiy kanal:</b> <a href=\"https://t.me/{main_ch_clean}\">{MAIN_CHANNEL}</a>\n"
        f"• <b>Bot manzili:</b> <a href=\"https://t.me/{bot_username}\">@{bot_username}</a>\n\n"
        f"💫 <i>Do'stona muhit, iliq muloqot va eng sara kontent doimo siz bilan birga bo'lsin!</i>"
    )


def main_inline_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🔍 Qidiruv / Kod", callback_data="user:search_hint"),
            InlineKeyboardButton(text="🎲 Tasodifiy", callback_data="user:random"),
        ],
        [
            InlineKeyboardButton(text="📢 Asosiy kanal", url=f"https://t.me/{MAIN_CHANNEL.lstrip('@')}"),
            InlineKeyboardButton(text="👤 Admin bilan bog'lanish", url=f"https://t.me/{OWNER_USER.lstrip('@')}"),
        ],
    ]
    if is_admin(user_id):
        rows.append([
            InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin:panel"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
            InlineKeyboardButton(text="📣 Reklama (3 bo'lim)", callback_data="admin:broadcast_menu"),
        ],
        [
            InlineKeyboardButton(text="🎬 Film / Anime joylash", callback_data="admin:add_menu"),
            InlineKeyboardButton(text="✏️ Tahrirlash (Edit)", callback_data="admin:edit_list"),
        ],
        [
            InlineKeyboardButton(text="🔒 Majburiy a'zo", callback_data="admin:req_channels"),
            InlineKeyboardButton(text="📡 Kanal / Chatlar", callback_data="admin:chats_info"),
        ],
        [
            InlineKeyboardButton(text="👮 Adminlar", callback_data="admin:admins_list"),
            InlineKeyboardButton(text="🤖 Bot holati", callback_data="admin:status"),
        ],
        [
            InlineKeyboardButton(text="✉️ Foydalanuvchiga xabar", callback_data="admin:direct_msg"),
            InlineKeyboardButton(text="📱 Chat Mini App", web_app=WebAppInfo(url=build_miniapp_url())),
        ],
        [
            InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="user:home"),
        ],
    ])


def broadcast_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="3/1 👤 Bot foydalanuvchilariga xabar", callback_data="bc:users")],
        [InlineKeyboardButton(text="3/2 📢 Kanal va chatlarga xabar", callback_data="bc:chats")],
        [InlineKeyboardButton(text="3/3 🌐 Barchaga xabar (Foydalanuvchi + Kanal/Chat)", callback_data="bc:all")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")],
    ])


def add_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍥 Anime", callback_data="addcat:anime"),
            InlineKeyboardButton(text="🧸 Multfilm", callback_data="addcat:multfilm"),
            InlineKeyboardButton(text="🎥 Kino", callback_data="addcat:kino"),
        ],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")],
    ])


def keep_old_kb(field_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Eski holaticha qoldirish", callback_data=f"editkeep:{field_name}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:panel")],
    ])


def build_content_caption(item: dict) -> str:
    cat_map = {"anime": "Anime", "multfilm": "Multfilm", "kino": "Kino"}
    cat_label = cat_map.get(item.get("category", ""), "Kontent")
    return (
        f"🎬 <b>{item['title']}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📂 <b>Turi:</b> {cat_label}\n"
        f"🎞 <b>Qismlar:</b> {item['episodes']}\n"
        f"🎭 <b>Janri:</b> {item['genre']}\n"
        f"📅 <b>Yili:</b> {item['year']}\n"
        f"🌐 <b>Tili:</b> {item['language']}\n"
        f"💿 <b>Sifati:</b> {item['quality']}\n"
        f"🔑 <b>Kod:</b> <code>{item['code']}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👇 Tomosha qilish uchun pastdagi tugmani bosing:"
    )


def watch_inline_kb(bot_username: str, code: str, include_ad_btn: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="▶️ Botda ko'rish",
                url=f"https://t.me/{bot_username}?start={code}"
            )
        ]
    ]
    if include_ad_btn:
        rows.append([
            InlineKeyboardButton(
                text="📣 Kanalga reklama sifatida yuborish",
                callback_data=f"adsend:{code}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def check_subscriptions(bot: Bot, user_id: int) -> list[dict]:
    if is_admin(user_id):
        return []
    req_list = db.list_required_channels()
    not_joined = []
    for ch in req_list:
        ref = ch["channel_ref"].strip()
        try:
            chat_id_or_user = int(ref) if ref.lstrip("-").isdigit() else ref
            member = await bot.get_chat_member(chat_id=chat_id_or_user, user_id=user_id)
            if member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ):
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return not_joined


def sub_required_kb(not_joined: list[dict], pending_code: str = "") -> InlineKeyboardMarkup:
    rows = []
    for ch in not_joined:
        rows.append([InlineKeyboardButton(text=f"➕ {ch['title']}", url=ch["url"])])
    rows.append([
        InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data=f"subcheck:{pending_code}"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_sub_gate(bot: Bot, chat_id: int, not_joined: list[dict], pending_code: str = "") -> None:
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "🔒 <b>Majburiy obuna!</b>\n\n"
            "Botdan foydalanish uchun quyidagi kanal va guruhlarga a'zo bo'ling. "
            "<b>Ushbu kanal/guruhlarga ulanganingizdan so'ng bot ishlaydi</b> "
            "(agar chiqib ketsangiz, qayta ulanmaguningizcha ishlamaydi):"
        ),
        reply_markup=sub_required_kb(not_joined, pending_code=pending_code),
    )


def _download_merged_video_sync(url: str, out_dir: str) -> str:
    out_tmpl = os.path.join(out_dir, "media.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": out_tmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "concurrent_fragment_downloads": 5,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filepath)
        mp4_path = base + ".mp4"
        if os.path.exists(mp4_path):
            return mp4_path
        if os.path.exists(filepath):
            return filepath
        for fname in os.listdir(out_dir):
            if fname.startswith("media."):
                return os.path.join(out_dir, fname)
    return ""


async def handle_link_video(message: Message, bot: Bot) -> None:
    match = URL_REGEX.search(message.text or "")
    if not match:
        return

    url = match.group(0).strip(").,]>\"'")
    status = await message.answer("⚡ Yuklanmoqda...")

    tmp_dir = tempfile.mkdtemp(prefix="dl_")
    try:
        file_path = await asyncio.to_thread(_download_merged_video_sync, url, tmp_dir)
        if not file_path or not os.path.exists(file_path):
            await status.edit_text("❌ Videoni yuklab bo'lmadi.")
            return

        await bot.send_video(
            chat_id=message.chat.id,
            video=FSInputFile(file_path),
            supports_streaming=True,
        )
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        await status.edit_text(f"❌ Xatolik: <code>{e}</code>")
    finally:
        for root_dir, _, files in os.walk(tmp_dir, topdown=False):
            for fname in files:
                try:
                    os.remove(os.path.join(root_dir, fname))
                except Exception:
                    pass
            try:
                os.rmdir(root_dir)
            except Exception:
                pass


async def send_movie_to_user(bot: Bot, chat_id: int, user_id: int, code: str, bot_username: str) -> None:
    not_joined = await check_subscriptions(bot, user_id)
    if not_joined:
        await send_sub_gate(bot, chat_id, not_joined, pending_code=code)
        return

    item = db.get_content_by_code(code.strip())
    if not item:
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ <b>{code}</b> kodli ma'lumot topilmadi.",
            reply_markup=main_inline_kb(user_id),
        )
        return

    caption = build_content_caption(item)
    await bot.send_photo(
        chat_id=chat_id,
        photo=item["poster_file_id"],
        caption=caption,
        reply_markup=watch_inline_kb(bot_username, item["code"], include_ad_btn=False),
    )
    try:
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=item["storage_channel"],
            message_id=item["storage_msg_id"],
        )
    except Exception as e:
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Faylni yuborishda xatolik: <code>{e}</code>",
        )


# ════════════════════════════════════════════════════════════════
#  MINI ILOVA → TELEGRAM (bot nomidan xabar yuborish)
# ════════════════════════════════════════════════════════════════

def verify_init_data(init_data: str) -> int | None:
    """Mini ilovadan kelgan initData ni Telegram imzosi bilan tekshiradi.
    To'g'ri bo'lsa foydalanuvchi ID sini qaytaradi, aks holda None."""
    try:
        pairs = dict(parse_qsl(init_data or "", keep_blank_values=True))
        recv_hash = pairs.pop("hash", "")
        if not recv_hash:
            return None
        check_str = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", TG_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        return int(json.loads(pairs["user"])["id"])
    except Exception:
        return None


async def to_ogg_opus(raw: bytes) -> bytes | None:
    """Brauzerda yozilgan ovozni (webm/mp4) Telegram voice formatiga (OGG/Opus) o'giradi.
    Serverda ffmpeg bo'lmasa None qaytaradi."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-i", "pipe:0",
            "-c:a", "libopus", "-b:a", "48k", "-f", "ogg", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate(raw)
        return out if proc.returncode == 0 and out else None
    except Exception:
        return None


async def execute_miniapp_payload(bot: Bot, payload: dict) -> tuple[bool, str, int | None]:
    action = payload.get("action")
    raw_target = str(payload.get("target_id", "")).strip()
    target_chat = parse_target_id(raw_target)
    reply_to = payload.get("reply_to")
    reply_id = int(reply_to) if str(reply_to or "").isdigit() else None

    if action == "send_direct":
        text_body = (payload.get("text") or "").strip()
        if not target_chat or not text_body:
            return False, "Manzil yoki matn bo'sh", None
        sent = await bot.send_message(
            chat_id=target_chat,
            text=fancy_text(text_body),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_id,
        )
        return True, f"Xabar {target_chat} ga yuborildi", sent.message_id

    if action == "send_voice_data":
        audio_b64 = payload.get("audio_base64") or ""
        if not target_chat or "," not in audio_b64:
            return False, "Ovoz fayli topilmadi", None
        raw_bytes = base64.b64decode(audio_b64.split(",", 1)[1])
        ogg = await to_ogg_opus(raw_bytes)
        if ogg:
            sent = await bot.send_voice(
                chat_id=target_chat,
                voice=BufferedInputFile(ogg, filename="voice.ogg"),
                reply_to_message_id=reply_id,
            )
        else:
            # ffmpeg yo'q bo'lsa — ovoz oddiy audio fayl bo'lib boradi
            sent = await bot.send_document(
                chat_id=target_chat,
                document=BufferedInputFile(raw_bytes, filename="voice.webm"),
                reply_to_message_id=reply_id,
            )
        return True, f"Ovozli xabar {target_chat} ga yuborildi", sent.message_id

    if action == "react_msg":
        msg_id = payload.get("message_id")
        emoji = (payload.get("emoji") or "").strip()
        if target_chat and msg_id and emoji:
            await bot.set_message_reaction(
                chat_id=target_chat,
                message_id=int(msg_id),
                reaction=[ReactionTypeEmoji(emoji=emoji)],
            )
            return True, "Reaksiya qo'yildi", None
        return False, "Reaksiya parametrlari noto'g'ri", None

    if action == "edit_sent_msg":
        msg_id = int(payload.get("message_id", 0))
        new_text = (payload.get("text") or "").strip()
        if target_chat and msg_id and new_text:
            await bot.edit_message_text(
                chat_id=target_chat,
                message_id=msg_id,
                text=fancy_text(new_text),
                parse_mode=ParseMode.HTML,
            )
            return True, "Xabar tahrirlandi", msg_id
        return False, "Tahrirlash parametrlari noto'g'ri", None

    if action == "delete_sent_msg":
        msg_id = int(payload.get("message_id", 0))
        if target_chat and msg_id:
            await bot.delete_message(chat_id=target_chat, message_id=msg_id)
            return True, "Xabar o'chirildi", msg_id
        return False, "O'chirish parametrlari noto'g'ri", None

    return False, "Noma'lum amal", None


@router.my_chat_member()
async def on_my_chat_member(event):
    chat = event.chat
    new_status = event.new_chat_member.status
    if new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        db.add_chat(chat.id, chat.title or str(chat.id), chat.type)


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_activity(message: Message, bot: Bot):
    try:
        db.add_chat(message.chat.id, message.chat.title or str(message.chat.id), message.chat.type)
    except Exception as e:
        print("db.add_chat xatosi:", e)
    if message.from_user and not message.from_user.is_bot:
        db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)

    txt = (message.text or "").strip()
    me = await bot.get_me()
    if txt == "/start" or txt.startswith(f"/start@{me.username}"):
        await message.answer(
            text=format_group_intro(message.chat.title or str(message.chat.id), me.username),
            disable_web_page_preview=True,
        )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    me = await bot.get_me()

    if message.chat.type in ("group", "supergroup"):
        db.add_chat(message.chat.id, message.chat.title or str(message.chat.id), message.chat.type)
        await message.answer(
            text=format_group_intro(message.chat.title or str(message.chat.id), me.username),
            disable_web_page_preview=True,
        )
        return

    clear_msg = await message.answer("♻️", reply_markup=ReplyKeyboardRemove())
    try:
        await clear_msg.delete()
    except Exception:
        pass

    parts = message.text.split(maxsplit=1)
    start_code = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""

    not_joined = await check_subscriptions(bot, message.from_user.id)
    if not_joined:
        await send_sub_gate(bot, message.chat.id, not_joined, pending_code=start_code)
        return

    if start_code:
        await send_movie_to_user(bot, message.chat.id, message.from_user.id, start_code, me.username)
        return

    await message.answer(
        text=format_welcome(message.from_user.full_name, me.username, is_admin(message.from_user.id)),
        reply_markup=main_inline_kb(message.from_user.id),
    )


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, bot: Bot, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        payload = json.loads(message.web_app_data.data)
    except Exception:
        return

    action = payload.get("action")
    if action == "stats":
        st = db.get_stats()
        await message.answer(
            f"📊 <b>Statistika</b>\n👤 Userlar: <b>{st['users']}</b>\n📢 Kanal/chatlar: <b>{st['chats']}</b>\n🎞 Kontentlar: <b>{st['contents']}</b>",
            reply_markup=admin_panel_kb(),
        )
        return
    if action == "req_channels":
        await message.answer("🔒 Majburiy a'zolik bo'limi:", reply_markup=admin_panel_kb())
        return
    if action == "bc_users":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="users")
        await message.answer("3/1 👤 Foydalanuvchilarga yuboriladigan xabarni kiriting:")
        return
    if action == "bc_chats":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="chats")
        await message.answer("3/2 📢 Kanal va chatlarga yuboriladigan xabarni kiriting:")
        return
    if action == "bc_all":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="all")
        await message.answer("3/3 🌐 Barchaga yuboriladigan xabarni kiriting:")
        return
    if action == "add_content":
        await message.answer("🎬 Bo'limni tanlang:", reply_markup=add_category_kb())
        return
    if action == "edit_content":
        await message.answer("✏️ Tahrirlash uchun Admin Paneldan <b>Tahrirlash (Edit)</b> ni bosing.", reply_markup=admin_panel_kb())
        return

    try:
        ok, info_text, tg_msg_id = await execute_miniapp_payload(bot, payload)
        if ok:
            extra = f" (TG ID: <code>{tg_msg_id}</code>)" if tg_msg_id else ""
            await message.answer(f"✅ {info_text}{extra}", reply_markup=admin_panel_kb())
        else:
            await message.answer(f"⚠️ {info_text}", reply_markup=admin_panel_kb())
    except Exception as e:
        await message.answer(f"❌ Telegram'ga yuborilmadi: <code>{e}</code>", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "user:home")
async def cb_user_home(call: CallbackQuery, bot: Bot, state: FSMContext):
    await state.clear()
    not_joined = await check_subscriptions(bot, call.from_user.id)
    if not_joined:
        await call.answer()
        await send_sub_gate(bot, call.message.chat.id, not_joined)
        return
    me = await bot.get_me()
    await call.message.edit_text(
        text=format_welcome(call.from_user.full_name, me.username, is_admin(call.from_user.id)),
        reply_markup=main_inline_kb(call.from_user.id),
    )
    await call.answer()


@router.callback_query(F.data == "user:search_hint")
async def cb_search_hint(call: CallbackQuery, bot: Bot):
    not_joined = await check_subscriptions(bot, call.from_user.id)
    if not_joined:
        await call.answer()
        await send_sub_gate(bot, call.message.chat.id, not_joined)
        return
    await call.message.answer(
        f"{EMOJI_FILM} <b>Havola, anime, multfilm yoki kino kodi / nomini yuboring</b>"
    )
    await call.answer()


@router.callback_query(F.data == "user:random")
async def cb_random_content(call: CallbackQuery, bot: Bot):
    not_joined = await check_subscriptions(bot, call.from_user.id)
    if not_joined:
        await call.answer()
        await send_sub_gate(bot, call.message.chat.id, not_joined)
        return
    items = db.list_contents(limit=50)
    if not items:
        await call.answer("Hozircha baza bo'sh!", show_alert=True)
        return
    chosen = random.choice(items)
    me = await bot.get_me()
    await call.answer()
    await send_movie_to_user(bot, call.message.chat.id, call.from_user.id, chosen["code"], me.username)


@router.callback_query(F.data.startswith("subcheck:"))
async def cb_subcheck(call: CallbackQuery, bot: Bot):
    pending_code = call.data.split(":", 1)[1].strip()
    not_joined = await check_subscriptions(bot, call.from_user.id)
    if not_joined:
        await call.answer("❌ Siz hali barcha kanal/guruhlarga a'zo bo'lmadingiz!", show_alert=True)
        return
    await call.answer("✅ Obuna tasdiqlandi! Bot ishga tushdi.", show_alert=False)
    try:
        await call.message.delete()
    except Exception:
        pass
    me = await bot.get_me()
    if pending_code:
        if URL_REGEX.search(pending_code):
            fake_msg = call.message.model_copy(update={"text": pending_code, "from_user": call.from_user})
            await handle_link_video(fake_msg, bot)
        else:
            await send_movie_to_user(bot, call.message.chat.id, call.from_user.id, pending_code, me.username)
    else:
        await call.message.answer(
            text=format_welcome(call.from_user.full_name, me.username, is_admin(call.from_user.id)),
            reply_markup=main_inline_kb(call.from_user.id),
        )


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer(f"❌ Bu bo'lim faqat adminlar uchun! Sizning ID: {call.from_user.id}", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("🛡 <b>Admin Panel</b>", reply_markup=admin_panel_kb())
    await call.answer()


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    st = db.get_stats()
    text = (
        "📊 <b>Bot Statistikasi</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 <b>Foydalanuvchilar soni:</b> {st['users']}\n"
        f"📢 <b>Kanal va chatlar soni:</b> {st['chats']}\n"
        f"🎞 <b>Bazadagi kontentlar:</b> {st['contents']}\n"
        f"🔒 <b>Majburiy kanallar/guruhlar:</b> {st['req_channels']}\n"
        f"👮 <b>Qo'shimcha adminlar:</b> {st['extra_admins']}"
    )
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:stats")],
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")],
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin:admins_list")
async def cb_admins_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    extra_rows = db.list_extra_admins()

    lines = ["👮 <b>Adminlar ro'yxati</b>", "━━━━━━━━━━━━━━━", "👑 <b>Asosiy adminlar:</b>"]
    for idx, aid in enumerate(BASE_ADMIN_IDS, 1):
        lines.append(f"{idx}. <code>{aid}</code> (Asosiy)")

    lines.append("\n➕ <b>Qo'shilgan adminlar:</b>")
    if not extra_rows:
        lines.append("<i>Hozircha qo'shimcha admin qo'shilmagan.</i>")
    else:
        for idx, r in enumerate(extra_rows, 1):
            lbl = f" — {r['label']}" if r.get("label") else ""
            lines.append(f"{idx}. <code>{r['user_id']}</code>{lbl}")

    kb_rows = [
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="admin:add_new")],
    ]
    for r in extra_rows:
        eid = int(r["user_id"])
        if eid not in BASE_ADMIN_IDS:
            kb_rows.append([
                InlineKeyboardButton(text=f"🗑 Olib tashlash: {eid}", callback_data=f"admindel:{eid}")
            ])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")])

    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data == "admin:add_new")
async def cb_admin_add_new(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AddAdminFSM.admin_input)
    await call.message.edit_text(
        "➕ <b>Yangi admin tayinlash</b>\n\n"
        "Yangi adminning <b>raqamli ID</b> sini, bazadagi <code>@username</code> sini yuboring "
        "yoki o'sha foydalanuvchidan kelgan xabarni <b>forward</b> qiling.\n\n"
        "<i>Yangi admin asosiy ikkita admindan keyingi o'rinda ro'yxatga qo'shiladi.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin:admins_list")]
        ])
    )
    await call.answer()


@router.message(AddAdminFSM.admin_input)
async def fsm_admin_add_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    target_id: int | None = None
    label = ""

    if message.forward_from:
        target_id = message.forward_from.id
        label = message.forward_from.full_name or (f"@{message.forward_from.username}" if message.forward_from.username else "")
    elif message.text:
        raw = message.text.strip()
        if raw.isdigit():
            target_id = int(raw)
        elif raw.startswith("@"):
            found = db.find_user_by_username(raw)
            if found:
                target_id = int(found["user_id"])
                label = f"{raw} ({found.get('full_name', '')})".strip()

    if not target_id:
        await message.answer(
            "❌ Foydalanuvchi topilmadi. Raqamli <b>ID</b> yuboring, xabar <b>forward</b> qiling yoki botdan o'tgan <code>@username</code> kiriting."
        )
        return

    if target_id in BASE_ADMIN_IDS:
        await state.clear()
        await message.answer(
            f"ℹ️ <code>{target_id}</code> allaqachon asosiy adminlar ro'yxatida.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👮 Adminlar ro'yxati", callback_data="admin:admins_list")]
            ])
        )
        return

    db.add_extra_admin(target_id, label)
    await state.clear()
    await message.answer(
        f"✅ Yangi admin qo'shildi: <code>{target_id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👮 Adminlar ro'yxati", callback_data="admin:admins_list")],
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")],
        ])
    )


@router.callback_query(F.data.startswith("admindel:"))
async def cb_admin_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    eid = int(call.data.split(":", 1)[1])
    if eid in BASE_ADMIN_IDS:
        await call.answer("Asosiy adminni o'chirib bo'lmaydi!", show_alert=True)
        return
    db.remove_extra_admin(eid)
    await call.answer("Admin olib tashlandi!", show_alert=False)
    await cb_admins_list(call)


@router.callback_query(F.data == "admin:direct_msg")
async def cb_direct_msg_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(DirectMsgFSM.target_user)
    await call.message.edit_text(
        "✉️ <b>Foydalanuvchiga xabar yuborish</b>\n\n"
        "Xabar yubormoqchi bo'lgan foydalanuvchining <b>Telegram ID</b> sini kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin:panel")]
        ])
    )
    await call.answer()


@router.message(DirectMsgFSM.target_user)
async def fsm_direct_target(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("❌ To'g'ri raqamli ID kiriting:")
        return
    await state.update_data(direct_target_id=int(raw))
    await state.set_state(DirectMsgFSM.message_text)
    await message.answer("📝 Yuboriladigan xabar matnini kiriting:")


@router.message(DirectMsgFSM.message_text)
async def fsm_direct_send(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    target_id = int(data["direct_target_id"])
    body = (message.text or "").strip()
    await state.clear()
    try:
        sent = await bot.send_message(
            chat_id=target_id,
            text=fancy_text(body),
            parse_mode=ParseMode.HTML,
        )
        await message.answer(
            f"✅ Xabar bot nomidan yuborildi!\n• Manzil: <code>{target_id}</code>\n• Xabar ID: <code>{sent.message_id}</code>",
            reply_markup=admin_panel_kb(),
        )
    except Exception as e:
        await message.answer(f"❌ Xabar yuborilmadi: <code>{e}</code>", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:chats_info")
async def cb_chats_info(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    st = db.get_stats()
    await call.message.edit_text(
        f"📡 <b>Kanal va Chatlar</b>\n━━━━━━━━━━━━━━━\n"
        f"📢 Asosiy kanal: <b>{MAIN_CHANNEL}</b>\n"
        f"💬 Bot qo'shilgan kanal/chatlar: <b>{st['chats']}</b> ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin:status")
async def cb_bot_status(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    await call.message.edit_text(
        "🤖 <b>Bot holati:</b> 🟢 Faol va barqaror ishlamoqda\n"
        f"🌐 <b>Mini App URL:</b> <code>{BASE_MINIAPP_URL}</code>\n"
        f"🔗 <b>API manzili:</b> <code>{BACKEND_API_URL or 'o‘rnatilmagan'}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
        ])
    )
    await call.answer()


@router.callback_query(F.data == "admin:req_channels")
async def cb_req_channels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    channels = db.list_required_channels()
    lines = [
        "🔒 <b>Majburiy a'zolik (Kanal va Guruhlar)</b>",
        "━━━━━━━━━━━━━━━",
        "<i>Bot o'sha kanal yoki guruhda admin bo'lishi kerak.</i>",
    ]
    kb_rows = []
    if not channels:
        lines.append("\nHozircha majburiy kanal/guruh qo'shilmagan.")
    else:
        lines.append("")
        for idx, ch in enumerate(channels, 1):
            lines.append(f"{idx}. <b>{ch['title']}</b> — <code>{ch['channel_ref']}</code>")
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"🗑 O'chirish: {ch['title'][:20]}",
                    callback_data=f"reqdel:{ch['channel_ref']}"
                )
            ])
    kb_rows.append([InlineKeyboardButton(text="➕ Majburiy kanal / guruh qo'shish", callback_data="reqadd:start")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")])

    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data == "reqadd:start")
async def cb_reqadd_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(ReqChannelFSM.channel_input)
    await call.message.edit_text(
        "➕ <b>Majburiy kanal yoki guruh qo'shish</b>\n\n"
        "Kanal yoki guruh <code>@username</code> yoki <code>-100...</code> ID sini yuboring.\n"
        "<i>Eslatma: Bot o'sha kanal/guruhda admin bo'lishi shart.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin:req_channels")]
        ])
    )
    await call.answer()


@router.message(ReqChannelFSM.channel_input)
async def fsm_req_channel_save(message: Message, bot: Bot, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    chat_target = int(raw) if raw.lstrip("-").isdigit() else raw
    bot_is_adm = False
    try:
        chat_info = await bot.get_chat(chat_target)
        title = chat_info.title or raw
        url = f"https://t.me/{chat_info.username}" if chat_info.username else f"https://t.me/{MAIN_CHANNEL.lstrip('@')}"
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat_info.id, user_id=me.id)
        bot_is_adm = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        title = raw
        url = f"https://t.me/{raw.lstrip('@')}" if raw.startswith("@") else f"https://t.me/{MAIN_CHANNEL.lstrip('@')}"

    db.add_required_channel(raw, title, url)
    await state.clear()
    warn = "" if bot_is_adm else "\n⚠️ <b>Diqqat:</b> Bot ushbu kanal/guruhda hali admin emas. Iltimos, botni admin qiling!"
    await message.answer(
        f"✅ Majburiy obuna qo'shildi: <b>{title}</b>{warn}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Majburiy a'zolikka qaytish", callback_data="admin:req_channels")]
        ])
    )


@router.callback_query(F.data.startswith("reqdel:"))
async def cb_req_channel_del(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ref = call.data.split(":", 1)[1]
    db.remove_required_channel(ref)
    await call.answer("O'chirildi!", show_alert=False)
    await cb_req_channels(call)


@router.callback_query(F.data == "admin:broadcast_menu")
async def cb_broadcast_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "📣 <b>Xabar tarqatish bo'limi</b>\n"
        "Kerakli tarqatish turini tanlang:",
        reply_markup=broadcast_menu_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("bc:"))
async def cb_bc_select(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    mode = call.data.split(":", 1)[1]
    labels = {
        "users": "3/1 — Barcha bot foydalanuvchilariga",
        "chats": "3/2 — Barcha kanal va chatlarga",
        "all": "3/3 — Barchaga (foydalanuvchilar + kanal/chatlar)",
    }
    await state.set_state(BroadcastFSM.message)
    await state.update_data(bc_mode=mode)
    await call.message.edit_text(
        f"✉️ <b>{labels.get(mode)}</b>\n\n"
        "Yuboriladigan xabarni (matn, rasm, video yoki post) yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:broadcast_menu")]
        ])
    )
    await call.answer()


@router.message(BroadcastFSM.message)
async def fsm_broadcast_send(message: Message, bot: Bot, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    mode = data.get("bc_mode", "users")
    await state.clear()

    targets: list[int] = []
    if mode in ("users", "all"):
        targets.extend(db.get_all_user_ids())
    if mode in ("chats", "all"):
        targets.extend(db.get_all_chat_ids())
        if MAIN_CHANNEL.startswith("@"):
            try:
                ch = await bot.get_chat(MAIN_CHANNEL)
                targets.append(ch.id)
            except Exception:
                pass

    unique_targets = list(dict.fromkeys(targets))
    status_msg = await message.answer(f"⏳ Xabar yuborilmoqda ({len(unique_targets)} manzil)...")

    sent = 0
    failed = 0
    for tid in unique_targets:
        try:
            await bot.copy_message(
                chat_id=tid,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n"
        f"📤 Yuborildi: <b>{sent}</b>\n"
        f"⚠️ Xato / bloklangan: <b>{failed}</b>",
        reply_markup=admin_panel_kb()
    )


@router.callback_query(F.data == "admin:add_menu")
async def cb_add_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "🎬 <b>Yangi kontent joylash</b>\nBo'limni tanlang (barchasi bir xil ketma-ketlikda to'ldiriladi):",
        reply_markup=add_category_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("addcat:"))
async def cb_add_cat(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    category = call.data.split(":", 1)[1]
    await state.set_state(AddContentFSM.title)
    await state.update_data(category=category)
    await call.message.edit_text("1/9 📝 <b>Nomini</b> kiriting (masalan: <i>Solo Leveling</i>):")
    await call.answer()


@router.message(AddContentFSM.title)
async def fsm_add_title(message: Message, state: FSMContext):
    await state.update_data(title=(message.text or "").strip())
    await state.set_state(AddContentFSM.poster)
    await message.answer("2/9 🖼 <b>Kanalga yuboriladigan fon rasmini (muqova rasm)</b> yuboring:")


@router.message(AddContentFSM.poster, F.photo)
async def fsm_add_poster(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(poster_file_id=photo_id)
    await state.set_state(AddContentFSM.episodes)
    await message.answer("3/9 🎞 <b>Nechta qismdan iboratligini</b> kiriting (masalan: <i>12 qism</i> yoki <i>1 film</i>):")


@router.message(AddContentFSM.episodes)
async def fsm_add_episodes(message: Message, state: FSMContext):
    await state.update_data(episodes=(message.text or "").strip())
    await state.set_state(AddContentFSM.genre)
    await message.answer("4/9 🎭 <b>Janrini</b> kiriting (masalan: <i>Action, Fantasy</i>):")


@router.message(AddContentFSM.genre)
async def fsm_add_genre(message: Message, state: FSMContext):
    await state.update_data(genre=(message.text or "").strip())
    await state.set_state(AddContentFSM.year)
    await message.answer("5/9 📅 <b>Chiqarilgan yilini</b> kiriting (masalan: <i>2025</i> yoki <i>2026</i>):")


@router.message(AddContentFSM.year)
async def fsm_add_year(message: Message, state: FSMContext):
    await state.update_data(year=(message.text or "").strip())
    await state.set_state(AddContentFSM.code)
    await message.answer("6/9 🔑 <b>Kodni</b> kiriting (masalan: <i>101</i>):")


@router.message(AddContentFSM.code)
async def fsm_add_code(message: Message, state: FSMContext):
    await state.update_data(code=(message.text or "").strip())
    await state.set_state(AddContentFSM.language)
    await message.answer("7/9 🌐 <b>Qaysi tildaligini</b> kiriting (masalan: <i>O'zbekcha</i>):")


@router.message(AddContentFSM.language)
async def fsm_add_language(message: Message, state: FSMContext):
    await state.update_data(language=(message.text or "").strip())
    await state.set_state(AddContentFSM.quality)
    await message.answer("8/9 💿 <b>Sifatini</b> kiriting (masalan: <i>720p</i> yoki <i>1080p</i>):")


@router.message(AddContentFSM.quality)
async def fsm_add_quality(message: Message, state: FSMContext):
    await state.update_data(quality=(message.text or "").strip())
    await state.set_state(AddContentFSM.storage_msg)
    await message.answer(
        "9/9 📦 Endi <b>videolar/fayllar joylangan kanal postini forward qiling</b> yoki o'sha kanalga yuborilgan xabarni shu yerga yuboring:"
    )


@router.message(AddContentFSM.storage_msg)
async def fsm_add_storage(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    if message.forward_from_chat:
        src_chat = str(message.forward_from_chat.id)
        src_msg_id = message.forward_from_message_id
    else:
        src_chat = str(message.chat.id)
        src_msg_id = message.message_id

    record = {
        **data,
        "storage_channel": src_chat,
        "storage_msg_id": src_msg_id,
    }
    db.save_content(record)
    await state.clear()

    me = await bot.get_me()
    caption = build_content_caption(record)
    await message.answer_photo(
        photo=record["poster_file_id"],
        caption="✅ <b>Saqlandi! Ko'rinishi:</b>\n\n" + caption,
        reply_markup=watch_inline_kb(me.username, record["code"], include_ad_btn=True),
    )


@router.callback_query(F.data.startswith("adsend:"))
async def cb_send_ad_to_channel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split(":", 1)[1]
    item = db.get_content_by_code(code)
    if not item:
        await call.answer("Kontent topilmadi!", show_alert=True)
        return

    me = await bot.get_me()
    caption = build_content_caption(item)
    await bot.send_photo(
        chat_id=MAIN_CHANNEL,
        photo=item["poster_file_id"],
        caption=caption,
        reply_markup=watch_inline_kb(me.username, item["code"], include_ad_btn=False),
    )
    await call.answer(f"📢 {MAIN_CHANNEL} kanaliga reklama yuborildi!", show_alert=True)


@router.callback_query(F.data == "admin:edit_list")
async def cb_edit_list(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    await state.clear()
    items = db.list_contents(limit=20)
    if not items:
        await call.message.edit_text(
            "📭 Tahrirlash uchun kontentlar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
            ])
        )
        await call.answer()
        return

    rows = []
    for it in items:
        rows.append([
            InlineKeyboardButton(
                text=f"[{it['code']}] {it['title']} ({it['quality']})",
                callback_data=f"editsel:{it['code']}"
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")])
    await call.message.edit_text(
        "✏️ <b>Tahrirlash bo'limi</b>\nO'zgartirmoqchi bo'lgan kontentni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await call.answer()


@router.callback_query(F.data.startswith("editsel:"))
async def cb_edit_select(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split(":", 1)[1]
    item = db.get_content_by_code(code)
    if not item:
        await call.answer("Topilmadi", show_alert=True)
        return

    await state.set_state(EditContentFSM.title)
    await state.update_data(edit_code=code, current_item=item)
    await call.message.edit_text(
        f"📝 <b>Yangi nomni kiriting</b>\nHozirgi nomi: <b>{item['title']}</b>",
        reply_markup=keep_old_kb("title")
    )
    await call.answer()


@router.callback_query(F.data.startswith("editkeep:"))
async def cb_edit_keep(call: CallbackQuery, state: FSMContext):
    field = call.data.split(":", 1)[1]
    data = await state.get_data()
    item = data["current_item"]
    await _advance_edit_step(call.message, state, item, field, keep_old=True)
    await call.answer()


@router.message(EditContentFSM.title)
async def fsm_edit_title(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["title"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "title", keep_old=False)


@router.message(EditContentFSM.poster, F.photo)
async def fsm_edit_poster(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["poster_file_id"] = message.photo[-1].file_id
    await _advance_edit_step(message, state, item, "poster", keep_old=False)


@router.message(EditContentFSM.episodes)
async def fsm_edit_episodes(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["episodes"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "episodes", keep_old=False)


@router.message(EditContentFSM.genre)
async def fsm_edit_genre(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["genre"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "genre", keep_old=False)


@router.message(EditContentFSM.year)
async def fsm_edit_year(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["year"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "year", keep_old=False)


@router.message(EditContentFSM.language)
async def fsm_edit_language(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["language"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "language", keep_old=False)


@router.message(EditContentFSM.quality)
async def fsm_edit_quality(message: Message, state: FSMContext):
    data = await state.get_data()
    item = data["current_item"]
    item["quality"] = (message.text or "").strip()
    await _advance_edit_step(message, state, item, "quality", keep_old=False)


async def _advance_edit_step(msg_obj: Message, state: FSMContext, item: dict, current_field: str, keep_old: bool):
    await state.update_data(current_item=item)
    steps = [
        ("title", EditContentFSM.poster, "🖼 <b>Yangi rasm yuboring</b> (fon rasmi)", "Rasm saqlandi"),
        ("poster", EditContentFSM.episodes, "🎞 <b>Yangi qismlar sonini kiriting</b>", f"Hozirgi: <b>{item['episodes']}</b>"),
        ("episodes", EditContentFSM.genre, "🎭 <b>Yangi janrni kiriting</b>", f"Hozirgi: <b>{item['genre']}</b>"),
        ("genre", EditContentFSM.year, "📅 <b>Yangi yilni kiriting</b>", f"Hozirgi: <b>{item['year']}</b>"),
        ("year", EditContentFSM.language, "🌐 <b>Yangi tilni kiriting</b>", f"Hozirgi: <b>{item['language']}</b>"),
        ("language", EditContentFSM.quality, "💿 <b>Yangi sifatni kiriting</b>", f"Hozirgi: <b>{item['quality']}</b>"),
    ]
    for f_name, next_state, prompt_text, cur_info in steps:
        if f_name == current_field:
            await state.set_state(next_state)
            await msg_obj.answer(f"{prompt_text}\n{cur_info}", reply_markup=keep_old_kb(next_state.state.split(":")[-1]))
            return

    db.save_content(item)
    await state.clear()
    await msg_obj.answer(
        "✅ <b>Ma'lumotlar yangilandi!</b>\n\n" + build_content_caption(item),
        reply_markup=admin_panel_kb()
    )


@router.message(F.text)
async def handle_text_search(message: Message, bot: Bot):
    if message.chat.type != "private":
        return
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    text = (message.text or "").strip()
    me = await bot.get_me()

    not_joined = await check_subscriptions(bot, message.from_user.id)
    if not_joined:
        await send_sub_gate(bot, message.chat.id, not_joined, pending_code=text)
        return

    if URL_REGEX.search(text):
        await handle_link_video(message, bot)
        return

    exact = db.get_content_by_code(text)
    if exact:
        await send_movie_to_user(bot, message.chat.id, message.from_user.id, text, me.username)
        return

    matches = db.search_contents(text)
    if matches:
        rows = [
            [InlineKeyboardButton(text=f"▶️ [{m['code']}] {m['title']} ({m['quality']})", callback_data=f"pick:{m['code']}")]
            for m in matches[:10]
        ]
        await message.answer(
            f"🔎 <b>«{text}»</b> bo'yicha topilgan natijalar:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
        return

    await message.answer(
        f"{EMOJI_FILM} <b>Havola, anime, multfilm yoki kino kodi / nomini yuboring</b>\n"
        f"❌ «{text}» topilmadi.",
        reply_markup=main_inline_kb(message.from_user.id)
    )


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_content(call: CallbackQuery, bot: Bot):
    not_joined = await check_subscriptions(bot, call.from_user.id)
    if not_joined:
        await call.answer()
        await send_sub_gate(bot, call.message.chat.id, not_joined)
        return
    code = call.data.split(":", 1)[1]
    me = await bot.get_me()
    await call.answer()
    await send_movie_to_user(bot, call.message.chat.id, call.from_user.id, code, me.username)


# ════════════════════════════════════════════════════════════════
#  WEB SERVER (mini ilova shu yerga so'rov yuboradi)
# ════════════════════════════════════════════════════════════════

def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


async def api_options(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=_cors_headers())


async def api_send_handler(request: web.Request) -> web.Response:
    if ACTIVE_BOT is None:
        return web.json_response({"ok": False, "error": "Bot tayyor emas"}, status=503, headers=_cors_headers())
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Noto'g'ri JSON"}, status=400, headers=_cors_headers())

    # Faqat admin Telegram ichidagi mini ilovadan yubora oladi
    uid = verify_init_data(payload.pop("init_data", ""))
    if not uid or not is_admin(uid):
        return web.json_response(
            {"ok": False, "error": "Ruxsat yo'q (admin emas yoki mini ilova Telegram ichida ochilmagan)"},
            status=403,
            headers=_cors_headers(),
        )

    if payload.get("action") == "broadcast":
        ok, info_text = await start_broadcast(
            ACTIVE_BOT, str(payload.get("mode", "")), payload.get("text", ""), uid
        )
        return web.json_response(
            {"ok": ok, "message": info_text, "error": "" if ok else info_text, "tg_message_id": None},
            headers=_cors_headers(),
        )

    try:
        ok, info_text, tg_msg_id = await execute_miniapp_payload(ACTIVE_BOT, payload)
        return web.json_response(
            {"ok": ok, "message": info_text, "error": "" if ok else info_text, "tg_message_id": tg_msg_id},
            headers=_cors_headers(),
        )
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=_cors_headers())


async def api_lists_handler(request: web.Request) -> web.Response:
    """Mini ilova guruh va kontaktlar ro'yxatini shu yerdan jonli oladi."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    uid = verify_init_data(payload.get("init_data", ""))
    if not uid or not is_admin(uid):
        return web.json_response({"ok": False, "error": "Ruxsat yo'q"}, status=403, headers=_cors_headers())
    return web.json_response({"ok": True, **load_lists()}, headers=_cors_headers())


async def api_messages_handler(request: web.Request) -> web.Response:
    """Mini ilova kelgan xabarlarni shu yerdan oladi."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    uid = verify_init_data(payload.get("init_data", ""))
    if not uid or not is_admin(uid):
        return web.json_response({"ok": False, "error": "Ruxsat yo'q"}, status=403, headers=_cors_headers())
    try:
        since = int(payload.get("since") or 0)
    except Exception:
        since = 0
    messages, last_seq, reset = fetch_inbox(since)
    return web.json_response(
        {"ok": True, "messages": messages, "last_seq": last_seq, "reset": reset},
        headers=_cors_headers(),
    )


async def start_web_server():
    app = web.Application(client_max_size=20 * 1024 * 1024)
    app.router.add_get("/", lambda req: web.Response(text="OK - AniKinolar Bot Running (inbox v1)"))
    app.router.add_options("/api/send", api_options)
    app.router.add_post("/api/send", api_send_handler)
    app.router.add_options("/api/lists", api_options)
    app.router.add_post("/api/lists", api_lists_handler)
    app.router.add_options("/api/messages", api_options)
    app.router.add_post("/api/messages", api_messages_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()


async def main():
    global ACTIVE_BOT
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN environment variable is missing!")
    db.init_db()
    init_inbox()
    await start_web_server()
    bot = Bot(
        token=TG_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    ACTIVE_BOT = bot
    dp = Dispatcher()
    dp.include_router(router)
    await bot.set_my_commands([])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
