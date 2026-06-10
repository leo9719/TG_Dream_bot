# -*- coding: utf-8 -*-
import os
import shutil
import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

# ========================= LOGGING =========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

user_language = {}
user_stats = {}
user_cooldowns = {}

# Простые тексты
def get_text(user_id, key):
    lang = user_language.get(user_id, 'ru')
    texts = {
        'ru': {
            'start': "👋 Выберите язык:",
            'welcome': "Отправь ссылку на видео или фото.",
        },
        'en': {
            'start': "👋 Choose language:",
            'welcome': "Send link to video or photo.",
        }
    }
    return texts[lang].get(key, texts['ru'].get(key))

# ========================= HANDLERS =========================
@dp.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])
    await message.answer(get_text(message.from_user.id, 'start'), reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    user_language[callback.from_user.id] = lang
    await callback.message.edit_text(get_text(callback.from_user.id, 'welcome'))

@dp.message(F.text)
async def handle_url(message: Message):
    await message.answer("Бот работает. Скоро добавлю скачивание.")

async def main():
    logger.info("🚀 Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())