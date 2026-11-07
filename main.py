import asyncio
import logging
import os
import aiosqlite
import warnings
from aiogram import Bot, Dispatcher
from aiogram.types import WebAppInfo, MenuButtonWebApp
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from handlers.user_handlers import router as user_router, db_start, WEBAPP_URL, TOKEN

warnings.filterwarnings("ignore", category=ResourceWarning)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

async def main():
    try:
        await db_start()
        print("🤖 Bot va server Webhook rejimida ishga tushirilmoqda...")
        
        webapp_button = MenuButtonWebApp(text="GrabCharakter", web_app=WebAppInfo(url=WEBAPP_URL))
        await bot.set_chat_menu_button(menu_button=webapp_button)
        
        # Routerni ulaymiz
        dp.include_router(user_router)
        
        app = web.Application(middlewares=[cors_middleware])
        
        # Veb-server marshrutlari (routes) user_handlers dan olinadi yoki shu yerda ulanadi
        from handlers.user_handlers import handle_home, handle_api_settings, handle_api_user_profile, handle_buy_waifu, handle_sell_waifu
        app.router.add_get("/", handle_home)
        app.router.add_get("/api/settings", handle_api_settings)
        app.router.add_get("/api/user", handle_api_user_profile)
        app.router.add_post("/api/buy", handle_buy_waifu)
        app.router.add_post("/api/sell", handle_sell_waifu)
        
        WEBHOOK_PATH = "/webhook"
        WEBHOOK_URL = f"{WEBAPP_URL}{WEBHOOK_PATH}"
        
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"🌐 Webhook server {port}-portda ishga tushdi!")

        await asyncio.Event().wait()
        
    finally:
        await bot.delete_webhook()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi.")
        
