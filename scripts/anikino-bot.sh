#!/bin/bash

###############################################################################
# AniKinolar boti: kino, anime va multfilmlar uchun Telegram bot.
#
# Asos: Lifailon/Kinozal-Bot (MIT litsenziya)
#       https://github.com/Lifailon/Kinozal-Bot
# Bu soddalashtirilgan versiya: Kinozal, qBittorrent, Transmission, Plex,
# VPN va TMDB qismlari olib tashlangan.
#
# Qanday ishlaydi:
#  1. Admin botga video yuboradi (izoh bilan). Bot uni kanalga joylaydi.
#     Kanaldagi post raqami (message_id) kinoning KODI bo'ladi.
#  2. Foydalanuvchi kod yuboradi. Bot kinoni kanaldan nusxalab yuboradi.
#  3. Alohida baza kerak emas: kanalning o'zi baza vazifasini bajaradi.
#
# Ishga tushirish:  bash anikino-bot.sh
###############################################################################

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
conf="$script_dir/anikino-bot.conf"

### Sozlamalarni o'qish (muhit o'zgaruvchilari konfigdan ustun turadi)
if [ -f "$conf" ]; then
    source "$conf"
fi

if [[ -z "$TG_TOKEN" || -z "$TG_CHAT" || -z "$TG_CHANNEL" ]]; then
    echo "Sozlamalar topilmadi (TG_TOKEN, TG_CHAT, TG_CHANNEL). anikino-bot.conf faylini tekshiring."
    exit 1
fi

API="https://api.telegram.org/bot$TG_TOKEN"
export TZ="${TIMEZONE:-Asia/Tashkent}"
BOT_USERNAME=""

################################ Yordamchilar ################################

function log {
    echo "[$(date '+%d.%m.%Y %H:%M:%S')] $*"
}

### Telegram API ga so'rov yuborish: tg <method> <curl parametrlari>
function tg {
    local method="$1"
    shift
    curl -s --max-time 60 -X POST "$API/$method" "$@"
}

### Foydalanuvchi admin ekanini tekshirish
function is_admin {
    local id="$1" a
    for a in ${TG_CHAT//,/ }; do
        [[ "$a" == "$id" ]] && return 0
    done
    return 1
}

### Oddiy matn yuborish (3-parametr: tugmalar JSON, ixtiyoriy)
function send_text {
    local chat="$1" text="$2" markup="$3"
    if [[ -n "$markup" ]]; then
        tg sendMessage -d "chat_id=$chat" --data-urlencode "text=$text" \
            --data-urlencode "reply_markup=$markup" > /dev/null
    else
        tg sendMessage -d "chat_id=$chat" --data-urlencode "text=$text" > /dev/null
    fi
}

################################## Obuna ######################################

### Foydalanuvchi kanalga obuna bo'lganini tekshirish
function is_subscribed {
    local uid="$1" status
    is_admin "$uid" && return 0
    status=$(tg getChatMember -d "chat_id=$TG_CHANNEL" -d "user_id=$uid" | jq -r '.result.status // "error"')
    [[ -z "$status" ]] && status="error"
    case "$status" in
        member|administrator|creator)
            return 0
        ;;
        error)
            # Odatda bot kanalda admin emas. Foydalanuvchini to'smaymiz.
            log "OGOHLANTIRISH: obunani tekshirib bo'lmadi (bot kanalda admin emasmi?)"
            return 0
        ;;
        *)
            return 1
        ;;
    esac
}

### "Kanalga obuna bo'ling" tugmalari
function join_markup {
    local code="$1"
    jq -nc \
        --arg t1 "📢 Kanalga obuna bo'lish" \
        --arg t2 "✅ Tekshirish" \
        --arg url "https://t.me/${TG_CHANNEL#@}" \
        --arg cb "check:$code" \
        '{inline_keyboard: [[{text: $t1, url: $url}], [{text: $t2, callback_data: $cb}]]}'
}

################################ Kino berish ##################################

### Kinoni foydalanuvchiga yuborish (kanaldagi postni nusxalaydi)
function deliver {
    local chat="$1" uid="$2" code="$3" res
    if ! is_subscribed "$uid"; then
        send_text "$chat" "Kinoni ko'rish uchun avval kanalimizga obuna bo'ling 👇" "$(join_markup "$code")"
        return
    fi
    res=$(tg copyMessage -d "chat_id=$chat" -d "from_chat_id=$TG_CHANNEL" -d "message_id=$code")
    if [[ "$(jq -r '.ok' <<< "$res")" == "true" ]]; then
        log "Kino yuborildi: kod $code -> $chat"
    else
        send_text "$chat" "❌ Bunday kodli kino topilmadi."
    fi
}

################################ Kino qo'shish ################################

### Admin yuborgan videoni kanalga joylash va kod berish
function add_movie {
    local upd="$1" chat="$2"
    local mid caption res code new_caption markup err

    mid=$(jq -r '.message.message_id' <<< "$upd")
    caption=$(jq -r '.message.caption // ""' <<< "$upd")

    if [[ -z "$caption" ]]; then
        send_text "$chat" "⚠️ Videoga izoh yozib qayta yuboring."$'\n\n'"Birinchi qator: kino nomi, qolgani: tavsif."$'\n\n'"Masalan:"$'\n'"Naruto (2002)"$'\n'"Janr: anime, jangari"$'\n'"Til: o'zbekcha"
        return
    fi

    # Kanalga joylash (video fayl qayta yuklanmaydi, nusxalanadi)
    res=$(tg copyMessage -d "chat_id=$TG_CHANNEL" -d "from_chat_id=$chat" -d "message_id=$mid")
    code=$(jq -r '.result.message_id // empty' <<< "$res")

    if [[ -z "$code" ]]; then
        err=$(jq -r '.description // "noma'\''lum xato"' <<< "$res")
        log "Kanalga joylab bo'lmadi: $err"
        send_text "$chat" "❌ Kanalga joylab bo'lmadi."$'\n'"Botni $TG_CHANNEL kanaliga admin qilib qo'shing (post joylash huquqi bilan)."$'\n\n'"Xato: $err"
        return
    fi

    # Postga kod va "Botda ko'rish" tugmasini qo'shish
    new_caption="${caption:0:900}"$'\n\n'"🔢 Kod: $code"$'\n'"📢 $TG_CHANNEL"
    markup=$(jq -nc \
        --arg t "▶️ Botda ko'rish" \
        --arg url "https://t.me/$BOT_USERNAME?start=$code" \
        '{inline_keyboard: [[{text: $t, url: $url}]]}')
    tg editMessageCaption -d "chat_id=$TG_CHANNEL" -d "message_id=$code" \
        --data-urlencode "caption=$new_caption" \
        --data-urlencode "reply_markup=$markup" > /dev/null

    log "Yangi kino qo'shildi: kod $code"
    send_text "$chat" "✅ Kanalga joylandi."$'\n'"🔢 Kod: $code"
}

################################ Xabarlarni qayta ishlash #####################

function welcome {
    local chat="$1" name="$2" uid="$3" text
    text="👋 Assalomu alaykum, $name!"$'\n\n'"🎬 Kino, anime va multfilmlar boti."$'\n\n'"🔢 Kino kodini yuboring."$'\n'"📢 Kodlar kanalda: $TG_CHANNEL"$'\n'"👤 Admin: $OWNER_USER"
    if is_admin "$uid"; then
        text+=$'\n\n'"🛠 Admin: kino qo'shish uchun videoni izoh bilan yuboring."$'\n'"Izohning birinchi qatori: kino nomi."
    fi
    send_text "$chat" "$text"
}

function handle_callback {
    local upd="$1" cb_id uid chat mid data code

    cb_id=$(jq -r '.callback_query.id' <<< "$upd")
    uid=$(jq -r '.callback_query.from.id' <<< "$upd")
    chat=$(jq -r '.callback_query.message.chat.id' <<< "$upd")
    mid=$(jq -r '.callback_query.message.message_id' <<< "$upd")
    data=$(jq -r '.callback_query.data // ""' <<< "$upd")

    if [[ "$data" == check:* ]]; then
        code="${data#check:}"
        if ! is_subscribed "$uid"; then
            tg answerCallbackQuery -d "callback_query_id=$cb_id" \
                --data-urlencode "text=❌ Siz hali obuna bo'lmagansiz!" \
                -d "show_alert=true" > /dev/null
            return
        fi
        tg answerCallbackQuery -d "callback_query_id=$cb_id" \
            --data-urlencode "text=✅ Rahmat!" > /dev/null
        tg deleteMessage -d "chat_id=$chat" -d "message_id=$mid" > /dev/null
        if [[ "$code" =~ ^[0-9]+$ && "$code" != "0" ]]; then
            deliver "$chat" "$uid" "$code"
        else
            send_text "$chat" "✅ Endi kino kodini yuboring."
        fi
    else
        tg answerCallbackQuery -d "callback_query_id=$cb_id" > /dev/null
    fi
}

function handle_update {
    local upd="$1"
    local chat uid name text media arg

    if [[ "$(jq 'has("callback_query")' <<< "$upd")" == "true" ]]; then
        handle_callback "$upd"
        return
    fi

    # Faqat shaxsiy suhbatlar
    if [[ "$(jq -r '.message.chat.type // ""' <<< "$upd")" != "private" ]]; then
        return
    fi

    chat=$(jq -r '.message.chat.id' <<< "$upd")
    uid=$(jq -r '.message.from.id' <<< "$upd")
    name=$(jq -r '.message.from.first_name // "foydalanuvchi"' <<< "$upd")
    text=$(jq -r '.message.text // ""' <<< "$upd")
    media=$(jq -r '.message | if (.video or .document or .animation) then "yes" else "no" end' <<< "$upd")

    # Video, fayl yoki animatsiya yuborilsa
    if [[ "$media" == "yes" ]]; then
        if is_admin "$uid"; then
            add_movie "$upd" "$chat"
        else
            send_text "$chat" "🔢 Kino kodini (raqam) yuboring."
        fi
        return
    fi

    case "$text" in
        /start*)
            arg="${text#/start}"
            arg="${arg# }"
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                deliver "$chat" "$uid" "$arg"
            else
                welcome "$chat" "$name" "$uid"
            fi
        ;;
        /help*)
            welcome "$chat" "$name" "$uid"
        ;;
        /*)
            # Noma'lum buyruqlarga javob bermaymiz
        ;;
        *)
            if [[ "$text" =~ ^[0-9]+$ ]]; then
                deliver "$chat" "$uid" "$text"
            elif [[ -n "$text" ]]; then
                send_text "$chat" "🔢 Iltimos, kino kodini (raqam) yuboring."$'\n'"Kodlar kanalda: $TG_CHANNEL"
            fi
        ;;
    esac
}

################################ Ishga tushirish ##############################

BOT_USERNAME=$(tg getMe | jq -r '.result.username // empty')
if [[ -z "$BOT_USERNAME" ]]; then
    echo "Telegram bilan bog'lanib bo'lmadi yoki TG_TOKEN noto'g'ri."
    exit 1
fi

# Agar ilgari webhook o'rnatilgan bo'lsa, getUpdates ishlashi uchun o'chiramiz
tg deleteWebhook > /dev/null

### Render uchun: kichik veb-server. Bepul tarifda port ochiq bo'lishi kerak,
### UptimeRobot shu manzilga ping yuborib, servisni uxlatmaydi.
if [[ -n "$PORT" ]]; then
    (
        while true; do
            printf 'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK' \
                | nc -l -p "$PORT" > /dev/null 2>&1 || sleep 1
        done
    ) &
    log "Veb-server $PORT portda ishlayapti"
fi

trap 'kill $(jobs -p) 2>/dev/null' EXIT

log "Bot ishga tushdi: @$BOT_USERNAME (kanal: $TG_CHANNEL)"

offset=0
while true; do
    updates=$(tg getUpdates -d "offset=$offset" -d "timeout=30" \
        --data-urlencode 'allowed_updates=["message","callback_query"]')

    if [[ "$(jq -r '.ok // false' <<< "$updates" 2>/dev/null)" != "true" ]]; then
        log "OGOHLANTIRISH: getUpdates javob bermadi, 5 soniyadan keyin qayta uriniladi"
        sleep 5
        continue
    fi

    while IFS= read -r upd; do
        [[ -z "$upd" ]] && continue
        offset=$(( $(jq -r '.update_id' <<< "$upd") + 1 ))
        handle_update "$upd"
    done < <(jq -c '.result[]' <<< "$updates")
done
