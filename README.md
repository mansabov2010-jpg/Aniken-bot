🎬 AniKinolar boti

Kino, anime va multfilmlar uchun oddiy Telegram bot. Toza Bash da yozilgan.

Asos: Lifailon/Kinozal-Bot (MIT litsenziya). Kinozal, torrent klientlari, Plex, VPN va TMDB qismlari olib tashlangan.

Qanday ishlaydi
Admin botga video yuboradi (izoh bilan). Bot uni kanalga joylaydi.
Kanaldagi post raqami kino kodi bo'ladi va postga yoziladi.
Foydalanuvchi kodni botga yuboradi (yoki postdagi "▶️ Botda ko'rish" tugmasini bosadi) va kinoni oladi.
Foydalanuvchi kanalga obuna bo'lmagan bo'lsa, avval obuna bo'lishni so'raydi.

Alohida baza yo'q: kanalning o'zi baza vazifasini bajaradi.

Kino qo'shish

Botga videoni yuboring. Izohning birinchi qatori kino nomi, qolgani tavsif:

Naruto (2002)
Janr: anime, jangari
Til: o'zbekcha

Bot kanalga joylaydi va sizga kodni yozadi.

Fayllar
Fayl	Vazifasi
scripts/anikino-bot.sh	Botning o'zi
scripts/anikino-bot.conf	Sozlamalar (token, adminlar, kanal)
Dockerfile	Docker/Render uchun
Render.com da bepul ishlatish
Repozitoriyni GitHub'da Private (yopiq) qiling (Settings → pastda "Change visibility"), chunki anikino-bot.conf ichida token bor.
Render → New → Web Service → GitHub repozitoriyingizni tanlang.
Sozlamalar:
Language: Docker
Instance Type: Free
Create Web Service tugmasini bosing. Build tugagach, loglarda Bot ishga tushdi yozuvi chiqadi.
Uxlab qolmasligi uchun: Render bepul tarifda 15 daqiqa so'rov bo'lmasa servisni uxlatadi. https://uptimerobot.com da bepul HTTP(s) monitor yarating: URL: Render bergan manzil (https://nomi.onrender.com), interval: 5 daqiqa.

Token o'rniga Render'ning Environment bo'limidan ham foydalanish mumkin (TG_TOKEN, TG_CHAT, TG_CHANNEL, OWNER_USER). U konfigdagi qiymatdan ustun turadi.

Kompyuterda yoki serverda ishlatish

curl, jq va bash kerak.

bash
bash scripts/anikino-bot.sh

Docker bilan:

bash
docker build -t anikino-bot .
docker run -d --name anikino-bot --restart=unless-stopped anikino-bot
docker logs anikino-bot --tail 50
Muhim
Botni @AniKinolar_kanal kanaliga admin qilib qo'shing (post joylash huquqi bilan).
Faqat o'zingizda huquqi bor yoki erkin litsenziyali kontentni joylang.
Kanaldagi postni o'chirsangiz, uning kodi ham ishlamay qoladi.
