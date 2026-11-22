# Yengil asosiy obraz
FROM alpine:latest

# Ishchi papka
WORKDIR /anikino-bot

# Kerakli dasturlar (bash, curl, jq; nc alpine ichida bor)
RUN apk add --no-cache bash coreutils curl jq tzdata

# Vaqt zonasi: Toshkent
ENV TZ=Asia/Tashkent
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Skript va sozlamalarni nusxalash
COPY scripts/anikino-bot.sh .
COPY scripts/anikino-bot.conf .

# Ishga tushirish huquqi
RUN chmod +x anikino-bot.sh

# Botni ishga tushirish (loglar konsolga chiqadi)
ENTRYPOINT ["bash", "./anikino-bot.sh"]
