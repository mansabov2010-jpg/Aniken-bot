import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers.user_handlers import router as user_router

async def main():
    bot = Bot(token="TOKENINGIZNI_YOZING")
    dp = Dispatcher()
    
    # Routerni ulaymiz
    dp.include_router(user_router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
  
