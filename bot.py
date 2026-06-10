# -*- coding: utf-8 -*-
import os
import shutil
import asyncio
import logging
import subprocess
import time
import random
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

MAX_VIDEO_SIZE = 350 * 1024 * 1024   # чуть снизили
MAX_DURATION = 20 * 60
COOLDOWN_SECONDS = 10                # увеличили паузу
DAILY_LIMIT = 30
MAX_DOWNLOAD_ATTEMPTS = 3

ALLOWED_DOMAINS = {"youtube.com", "youtu.be", "instagram.com", "tiktok.com", "vm.tiktok.com"}

COOKIES_FILE = "cookies.txt"

# ========================= LOGGING =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========================= LANGUAGES =========================
user_language = {}

TEXTS = {
    'ru': {
        'start': "👋 <b>Добро пожаловать в SaveReelBot!</b>\n\nВыберите язык:",
        'welcome': "Отправь ссылку на видео или фото.",
        'too_fast': "⏳ Подожди немного между запросами.",
        'limit_exceeded': "⛔️ Дневной лимит 30 скачиваний исчерпан.",
        'unsupported': "❌ Поддерживаются только Instagram, TikTok, YouTube.",
        'downloading': "⬇️ Скачиваю...",
        'done': "✅ Готово!",
        'error': "❌ Не удалось скачать. Попробуй другую ссылку."
    },
    'en': {
        'start': "👋 <b>Welcome to SaveReelBot!</b>\n\nChoose language:",
        'welcome': "Send a link to video or photo.",
        'too_fast': "⏳ Please wait between requests.",
        'limit_exceeded': "⛔️ Daily limit of 30 downloads exceeded.",
        'unsupported': "❌ Only Instagram, TikTok, YouTube supported.",
        'downloading': "⬇️ Downloading...",
        'done': "✅ Done!",
        'error': "❌ Failed to download. Try another link."
    }
}

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
        logger.info("✅ yt-dlp успешно обновлён")
    except Exception as e:
        logger.warning(f"Не удалось обновить yt-dlp: {e}")

def get_text(user_id: int, key: str, **kwargs):
    lang = user_language.get(user_id, 'ru')
    text = TEXTS[lang].get(key, TEXTS['ru'].get(key, key))
    return text.format(**kwargs)

def is_allowed_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in ALLOWED_DOMAINS)
    except:
        return False

def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_SECONDS:
        return False
    user_cooldowns[user_id] = now
    return True

def check_daily_limit(user_id: int) -> bool:
    now = datetime.now()
    if user_id not in user_stats:
        user_stats[user_id] = {"count": 0, "reset_time": now + timedelta(days=1)}
    if now > user_stats[user_id]["reset_time"]:
        user_stats[user_id] = {"count": 0, "reset_time": now + timedelta(days=1)}
    return user_stats[user_id]["count"] < DAILY_LIMIT

def get_user_folder(user_id: int) -> Path:
    folder = BASE_DOWNLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def cleanup_folder(folder: Path):
    shutil.rmtree(folder, ignore_errors=True)

# ========================= DOWNLOAD (с пониженным риском) =========================
async def download_media(url: str, output_dir: Path, status_message: Message, is_audio: bool = False):
    await asyncio.sleep(random.uniform(1.5, 3.0))  # случайная задержка

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
                "retries": 4,
                "socket_timeout": 50,
                "filesize_limit": MAX_VIDEO_SIZE,
            }

            if os.path.exists(COOKIES_FILE):
                ydl_opts["cookiefile"] = COOKIES_FILE

            if is_audio:
                ydl_opts.update({"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]})
            else:
                ydl_opts.update({"format": "best[height<=1080]/best"})   # самый безопасный вариант

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        except Exception as e:
            logger.warning(f"Попытка {attempt} failed: {e}")
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(random.uniform(4, 8))
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
        get_text(callback.from_user.id, 'welcome'),
        parse_mode="HTML"
    )


@dp.message(F.text)
async def handle_url(message: Message):
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

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text(get_text(user_id, 'error'))

    finally:
        cleanup_folder(user_folder)


async def main():
    update_ytdlp()
    check_cookies()
    logger.info("🚀 SaveReelBot запущен (режим пониженного риска)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())