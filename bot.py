# -*- coding: utf-8 -*-
import os
import re
import time
import shutil
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
import yt_dlp

# ========================= CONFIG =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

MAX_VIDEO_SIZE = 400 * 1024 * 1024
MAX_DURATION = 25 * 60
COOLDOWN_SECONDS = 8
DAILY_LIMIT = 30

ALLOWED_DOMAINS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
}

COOKIES_FILE = "cookies.txt"

# ========================= LOGGING =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================= BOT =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

user_stats = {}
user_cooldowns = {}

# ========================= COOKIES CHECK =========================
def check_cookies():
    if os.path.exists(COOKIES_FILE):
        size = os.path.getsize(COOKIES_FILE) / 1024
        logger.info(f"✅ Cookies Instagram найдены ({size:.1f} KB)")
        return True
    else:
        logger.warning("⚠️ Файл cookies.txt НЕ найден! Instagram будет работать хуже.")
        return False

# ========================= HELPERS =========================
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

# ========================= DOWNLOAD =========================
def download_media(url: str, output_dir: Path, is_audio: bool = False):
    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "quiet": False,
        "retries": 5,
        "socket_timeout": 40,
    }

    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    if is_audio:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[height<=1080][filesize<400M]/best[height<=1080]/best",
            "noplaylist": True,
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# ========================= COMMANDS =========================
@dp.message(CommandStart())
async def start(message: Message):
    cookies_status = "✅ Cookies Instagram активны" if os.path.exists(COOKIES_FILE) else "⚠️ Cookies не найдены"
    await message.answer(
        f"<b>SaveReelBot</b>\n\n"
        f"Отправь ссылку на пост из Instagram, TikTok или YouTube.\n"
        f"Поддержка: видео • фото • карусели • MP3\n\n"
        f"{cookies_status}\n"
        f"Лимит: 30 скачиваний в сутки.",
        parse_mode="HTML"
    )

@dp.message(Command("stats"))
async def stats(message: Message):
    user_id = message.from_user.id
    count = user_stats.get(user_id, {}).get("count", 0)
    await message.answer(
        f"<b>Статистика</b>\nСкачано сегодня: <b>{count}</b> / {DAILY_LIMIT}",
        parse_mode="HTML"
    )

# ========================= MAIN HANDLER =========================
@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        return await message.answer("⏳ Подожди 8 секунд между запросами.")
    if not check_daily_limit(user_id):
        return await message.answer("⛔️ Дневной лимит (30) исчерпан. Приходи завтра!")

    if not is_allowed_url(url):
        return await message.answer("❌ Поддерживаются только Instagram, TikTok, YouTube.")

    status = await message.answer("⏳ Проверяю...")

    user_folder = get_user_folder(user_id)

    try:
        is_audio = any(x in url.lower() for x in ["music", "audio", "mp3"])
        await status.edit_text("⬇️ Скачиваю...")

        file_path = await asyncio.to_thread(download_media, url, user_folder, is_audio)

        user_stats[user_id]["count"] += 1

        if file_path.endswith('.mp3'):
            await message.answer_audio(FSInputFile(file_path), caption="✅ Готово!")
        else:
            await message.answer_document(FSInputFile(file_path), caption="✅ Готово! @SaveReelBot")

        await status.delete()
        logger.info(f"User {user_id} downloaded: {url}")

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}")
        error = str(e).lower()
        if any(x in error for x in ["private", "unavailable", "login", "restricted"]):
            await status.edit_text("❌ Контент приватный или недоступен.")
        else:
            await status.edit_text("❌ Не удалось скачать. Попробуй другую ссылку.")

    finally:
        cleanup_folder(user_folder)


async def main():
    cookies_ok = check_cookies()
    logger.info("🚀 SaveReelBot запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())