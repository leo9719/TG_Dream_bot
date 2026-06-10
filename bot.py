# -*- coding: utf-8 -*-
import os
import shutil
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp

# ========================= CONFIG =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

MAX_VIDEO_SIZE = 400 * 1024 * 1024
MAX_DURATION = 25 * 60
COOLDOWN_SECONDS = 6
DAILY_LIMIT = 30
MAX_DOWNLOAD_ATTEMPTS = 3

ALLOWED_DOMAINS = {"youtube.com", "youtu.be", "instagram.com", "tiktok.com", "vm.tiktok.com"}

COOKIES_FILE = "cookies.txt"

# ========================= LANGUAGES =========================
user_language = {}  # user_id: 'ru' or 'en'

TEXTS = {
    'ru': {
        'start': "👋 <b>Добро пожаловать в SaveReelBot!</b>\n\nВыберите язык:",
        'help': "📋 <b>Как пользоваться:</b>\n\nПросто отправь ссылку на пост.",
        'stats': "📊 Скачано сегодня: <b>{count}</b> / {limit}",
        'limit_exceeded': "⛔️ Дневной лимит (30) исчерпан.",
        'too_fast': "⏳ Подожди 6 секунд между запросами.",
        'unsupported': "❌ Поддерживаются только Instagram, TikTok, YouTube.",
        'downloading': "⬇️ Скачиваю...",
        'done': "✅ Готово!",
        'error': "❌ Не удалось скачать. Попробуй другую ссылку."
    },
    'en': {
        'start': "👋 <b>Welcome to SaveReelBot!</b>\n\nChoose language:",
        'help': "📋 <b>How to use:</b>\n\nJust send the link.",
        'stats': "📊 Downloaded today: <b>{count}</b> / {limit}",
        'limit_exceeded': "⛔️ Daily limit (30) exceeded.",
        'too_fast': "⏳ Please wait 6 seconds between requests.",
        'unsupported': "❌ Only Instagram, TikTok, YouTube are supported.",
        'downloading': "⬇️ Downloading...",
        'done': "✅ Done!",
        'error': "❌ Failed to download. Try another link."
    }
}

# ========================= BOT =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

user_stats = {}
user_cooldowns = {}

# ========================= UTILS =========================
def check_cookies():
    if os.path.exists(COOKIES_FILE):
        size = os.path.getsize(COOKIES_FILE) / 1024
        logger.info(f"✅ Cookies Instagram найдены ({size:.1f} KB)")
        return True
    logger.warning("⚠️ cookies.txt не найден")
    return False

def update_ytdlp():
    try:
        logger.info("🔄 Обновляем yt-dlp...")
        subprocess.run(["pip", "install", "--upgrade", "yt-dlp"], capture_output=True, text=True, timeout=60, check=True)
        logger.info("✅ yt-dlp обновлён")
    except Exception as e:
        logger.warning(f"yt-dlp update failed: {e}")

def get_text(user_id: int, key: str, **kwargs):
    lang = user_language.get(user_id, 'ru')
    text = TEXTS[lang].get(key, TEXTS['ru'].get(key, key))
    return text.format(**kwargs)

# ========================= DOWNLOAD (без изменений) =========================
async def download_media(url: str, output_dir: Path, status_message: Message, is_audio: bool = False):
    # ... (оставляем ту же функцию, что была раньше)
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        percent = float(d.get('_percent_str', '0').strip('%'))
                        asyncio.create_task(status_message.edit_text(f"⬇️ {get_text(status_message.chat.id, 'downloading')} {percent:.1f}%"))
                    except:
                        pass

            ydl_opts = {
                "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
                "progress_hooks": [progress_hook],
                "retries": 5,
                "socket_timeout": 40,
                "filesize_limit": MAX_VIDEO_SIZE,
            }

            if os.path.exists(COOKIES_FILE):
                ydl_opts["cookiefile"] = COOKIES_FILE

            if is_audio:
                ydl_opts.update({"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]})
            else:
                ydl_opts.update({"format": f"bestvideo[filesize<{MAX_VIDEO_SIZE//1024//1024}M][height<=1080]/best[height<=1080]/best"})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(3)
            else:
                raise

# ========================= HANDLERS =========================
@dp.message(CommandStart())
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])
    await message.answer(get_text(message.from_user.id, 'start'), reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    user_language[callback.from_user.id] = lang
    await callback.message.edit_text(
        "✅ Язык успешно установлен!\n\nОтправь ссылку на видео или пост.",
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(get_text(message.from_user.id, 'help'), parse_mode="HTML")


@dp.message(Command("stats"))
async def stats(message: Message):
    user_id = message.from_user.id
    count = user_stats.get(user_id, {}).get("count", 0)
    await message.answer(get_text(user_id, 'stats', count=count, limit=DAILY_LIMIT), parse_mode="HTML")


@dp.message(F.text)
async def handle_url(message: Message):
    # ... (остальная логика handle_url остаётся почти такой же)
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        return await message.answer(get_text(user_id, 'too_fast'))
    if not check_daily_limit(user_id):
        return await message.answer(get_text(user_id, 'limit_exceeded'))

    if not is_allowed_url(url):
        return await message.answer(get_text(user_id, 'unsupported'))

    status = await message.answer(get_text(user_id, 'downloading'))

    user_folder = get_user_folder(user_id)

    try:
        is_audio = any(x in url.lower() for x in ["music", "audio", "mp3", "song", "песня", "музыка"])
        file_path = await download_media(url, user_folder, status, is_audio)

        user_stats[user_id]["count"] += 1

        if file_path.endswith('.mp3'):
            await message.answer_audio(FSInputFile(file_path), caption=get_text(user_id, 'done'))
        else:
            await message.answer_document(FSInputFile(file_path), caption=get_text(user_id, 'done'))

        await status.delete()

    except Exception:
        await status.edit_text(get_text(user_id, 'error'))

    finally:
        cleanup_folder(user_folder)

async def main():
    update_ytdlp()
    check_cookies()
    logger.info("🚀 SaveReelBot запущен с выбором языка!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())