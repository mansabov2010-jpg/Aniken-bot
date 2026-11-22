import asyncio
import base64
import json
import os
import random
import re
import tempfile
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
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
MINIAPP_URL = clean_url(
    os.getenv("MINIAPP_URL", ""),
    "https://mansabov2010-jpg.github.io/Aniken-bot/miniapp/index.html"
)
PORT = int(os.getenv("PORT", "8080"))

EMOJI_WAVE = "👋"
EMOJI_FILM = "🎞"
EMOJI_BOT = "🤖"
URL_REGEX = re.compile(r"https?://\S+")

router = Router()


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


def format_welcome(full_name: str, bot_username: str, is_adm: bool) -> str:
    base = (
        f"{EMOJI_WAVE} Xush kelibsiz, <b>{full_name}</b>!\n\n"
        f"{EMOJI_FILM} <b>Havola, anime, multfilm yoki kino kodi / nomini yuboring</b>\n\n"
        f"{EMOJI_BOT} Ushbu bot <b>@{bot_username}</b> | Admin: <b>{OWNER_USER}</b>"
    )
    if is_adm:
        base += "\n\n🛡 <i>Admin huquqi faol. Barcha boshqaruv bo'limlari Admin Panel ichida.</i>"
    return base


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
            InlineKeyboardButton(text="📱 Chat Mini App", web_app=WebAppInfo(url=MINIAPP_URL)),
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


@router.my_chat_member()
async def on_my_chat_member(event):
    chat = event.chat
    new_status = event.new_chat_member.status
    if new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        db.add_chat(chat.id, chat.title or str(chat.id), chat.type)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    me = await bot.get_me()

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


@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛡 <b>Admin Panel</b>", reply_markup=admin_panel_kb())


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
    elif action == "req_channels":
        await message.answer("🔒 Majburiy a'zolik bo'limi:", reply_markup=admin_panel_kb())
    elif action == "bc_users":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="users")
        await message.answer("3/1 👤 Foydalanuvchilarga yuboriladigan xabarni kiriting:")
    elif action == "bc_chats":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="chats")
        await message.answer("3/2 📢 Kanal va chatlarga yuboriladigan xabarni kiriting:")
    elif action == "bc_all":
        await state.set_state(BroadcastFSM.message)
        await state.update_data(bc_mode="all")
        await message.answer("3/3 🌐 Barchaga yuboriladigan xabarni kiriting:")
    elif action == "add_content":
        await message.answer("🎬 Bo'limni tanlang:", reply_markup=add_category_kb())
    elif action == "edit_content":
        await message.answer("✏️ Tahrirlash uchun Admin Paneldan <b>Tahrirlash (Edit)</b> ni bosing.", reply_markup=admin_panel_kb())
    elif action == "send_direct":
        raw_target = str(payload.get("target_id", "")).strip()
        target_chat = int(raw_target) if raw_target.lstrip("-").isdigit() else raw_target
        text_body = (payload.get("text") or "").strip()
        reply_mid = payload.get("reply_to_message_id")
        if target_chat and text_body:
            try:
                await bot.send_message(
                    chat_id=target_chat,
                    text=text_body,
                    reply_to_message_id=int(reply_mid) if reply_mid else None,
                )
                await message.answer(f"✅ Xabar bot nomidan <code>{target_chat}</code> ga yuborildi!", reply_markup=admin_panel_kb())
            except Exception as e:
                await message.answer(f"❌ Yuborishda xato: <code>{e}</code>", reply_markup=admin_panel_kb())
    elif action == "send_voice_data":
        raw_target = str(payload.get("target_id", "")).strip()
        target_chat = int(raw_target) if raw_target.lstrip("-").isdigit() else raw_target
        audio_b64 = payload.get("audio_base64") or ""
        if target_chat and "," in audio_b64:
            try:
                raw_bytes = base64.b64decode(audio_b64.split(",", 1)[1])
                await bot.send_voice(
                    chat_id=target_chat,
                    voice=BufferedInputFile(raw_bytes, filename="voice.ogg"),
                )
                await message.answer(f"🎙 Ovozli xabar <code>{target_chat}</code> ga yuborildi!", reply_markup=admin_panel_kb())
            except Exception as e:
                await message.answer(f"❌ Ovozli xabar yuborilmadi: <code>{e}</code>", reply_markup=admin_panel_kb())
    elif action == "react_msg":
        raw_target = str(payload.get("target_id", "")).strip()
        target_chat = int(raw_target) if raw_target.lstrip("-").isdigit() else raw_target
        msg_id = payload.get("message_id")
        emoji = (payload.get("emoji") or "").strip()
        if target_chat and msg_id and emoji:
            try:
                await bot.set_message_reaction(
                    chat_id=target_chat,
                    message_id=int(msg_id),
                    reaction=[ReactionTypeEmoji(emoji=emoji)],
                )
            except Exception:
                pass
    elif action == "edit_sent_msg":
        raw_target = str(payload.get("target_id", "")).strip()
        target_chat = int(raw_target) if raw_target.lstrip("-").isdigit() else raw_target
        msg_id = int(payload.get("message_id", 0))
        new_text = (payload.get("text") or "").strip()
        if target_chat and msg_id and new_text:
            try:
                await bot.edit_message_text(chat_id=target_chat, message_id=msg_id, text=new_text)
                await message.answer("✏️ Xabar tahrirlandi!", reply_markup=admin_panel_kb())
            except Exception as e:
                await message.answer(f"❌ Tahrirlashda xato: <code>{e}</code>", reply_markup=admin_panel_kb())
    elif action == "delete_sent_msg":
        raw_target = str(payload.get("target_id", "")).strip()
        target_chat = int(raw_target) if raw_target.lstrip("-").isdigit() else raw_target
        msg_id = int(payload.get("message_id", 0))
        if target_chat and msg_id:
            try:
                await bot.delete_message(chat_id=target_chat, message_id=msg_id)
                await message.answer("🗑 Xabar o'chirildi!", reply_markup=admin_panel_kb())
            except Exception as e:
                await message.answer(f"❌ O'chirishda xato: <code>{e}</code>", reply_markup=admin_panel_kb())


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
            text=body,
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
        f"🌐 <b>Mini App URL:</b> <code>{MINIAPP_URL}</code>",
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


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="OK - AniKinolar Bot Running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()


async def main():
    if not TG_TOKEN:
        raise RuntimeError("TG_TOKEN environment variable is missing!")
    db.init_db()
    await start_web_server()
    bot = Bot(
        token=TG_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
