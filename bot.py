# -*- coding: utf-8 -*-
import os
import shutil
import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

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

# ========================= TEXTS =========================
def get_text(user_id, key):
    lang = user_language.get(user_id, 'ru')
    texts = {
        'ru': {
            'start': "👋 Выберите язык:",
            'welcome': "Отправь ссылку — бот скачает.",
            'downloading': "⬇️ Скачиваю...",
            'done': "✅ Готово!",
            'error': "❌ Не удалось скачать."
        },
        'en': {
            'start': "👋 Choose language:",
            'welcome': "Send link — bot will download.",
            'downloading': "⬇️ Downloading...",
            'done': "✅ Done!",
            'error': "❌ Failed to download."
        }
    }
    return texts[lang].get(key, texts['ru'].get(key))

# ========================= DOWNLOAD =========================
def sync_download(url, output_dir):
    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "format": "best[height<=1080]",
        "retries": 3,
        "quiet": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

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
    user_language[callback.from_user.id] = callback.data.split("_")[1]
    await callback.message.edit_text(get_text(callback.from_user.id, 'welcome'))

@dp.message(F.text)
async def handle_url(message: Message):
    url = message.text.strip()
    status = await message.answer(get_text(message.from_user.id, 'downloading'))

    user_folder = BASE_DOWNLOAD_DIR / str(message.from_user.id)
    user_folder.mkdir(parents=True, exist_ok=True)

    try:
        file_path = await asyncio.to_thread(sync_download, url, user_folder)
        await message.answer_document(FSInputFile(file_path), caption=get_text(message.from_user.id, 'done'))
        await status.delete()
    except Exception as e:
        logger.error(e)
        await status.edit_text(get_text(message.from_user.id, 'error'))

async def main():
    logger.info("🚀 Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())