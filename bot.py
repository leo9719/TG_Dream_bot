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

# ==================== ОГРАНИЧЕНИЯ ====================
MAX_VIDEO_SIZE = 400 * 1024 * 1024    # 400 МБ
MAX_DURATION = 25 * 60                # 25 минут
COOLDOWN_SECONDS = 8
DAILY_LIMIT = 30                      # Лимит скачиваний в сутки
# ====================================================

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
    
    if user_stats[user_id]["count"] >= DAILY_LIMIT:
        return False
    return True


def get_user_folder(user_id: int) -> Path:
    folder = BASE_DOWNLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_folder(folder: Path):
    shutil.rmtree(folder, ignore_errors=True)


def download_media(url: str, output_dir: Path, is_audio: bool = False):
    if is_audio:
        ydl_opts = {
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "quiet": False,
            "retries": 5,
        }
    else:
        ydl_opts = {
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "format": "bestvideo[height<=1080][filesize<400M]/best[height<=1080]/best",
            "noplaylist": True,
            "quiet": False,
            "retries": 5,
            "socket_timeout": 40,
        }

    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# ========================= COMMANDS =========================
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "<b>SaveReelBot</b>\n\n"
        "Отправь ссылку на пост из Instagram, TikTok или YouTube.\n"
        "Поддержка: видео • фото • карусели • аудио (MP3)\n\n"
        "Лимит: 30 скачиваний в сутки.",
        parse_mode="HTML"
    )


@dp.message(Command("stats"))
async def stats(message: Message):
    user_id = message.from_user.id
    count = user_stats.get(user_id, {}).get("count", 0)
    await message.answer(
        f"<b>Ваша статистика</b>\n\n"
        f"Скачано сегодня: <b>{count}</b> / {DAILY_LIMIT}\n"
        f"Лимит обновится завтра.",
        parse_mode="HTML"
    )


# ========================= MAIN HANDLER =========================
@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        await message.answer("⏳ Подожди 8 секунд между запросами.")
        return

    if not check_daily_limit(user_id):
        await message.answer("⛔️ Вы исчерпали дневной лимит (30 скачиваний). Приходите завтра!")
        return

    if not is_allowed_url(url):
        await message.answer("❌ Поддерживаются только Instagram, TikTok и YouTube.")
        return

    status = await message.answer("⏳ Проверяю...")

    user_folder = get_user_folder(user_id)

    try:
        is_audio = any(word in url.lower() for word in ["music", "audio", "mp3"])

        await status.edit_text("⬇️ Скачиваю...")

        file_path = await asyncio.to_thread(download_media, url, user_folder, is_audio)

        if not os.path.exists(file_path):
            raise Exception("File not found")

        user_stats[user_id]["count"] += 1

        if file_path.endswith('.mp3'):
            await message.answer_audio(
                audio=FSInputFile(file_path),
                caption="✅ Готово! @SaveReelBot"
            )
        else:
            await message.answer_document(
                document=FSInputFile(file_path),
                caption="✅ Готово! @SaveReelBot"
            )

        await status.delete()
        logger.info(f"User {user_id} downloaded: {url}")

    except Exception as e:
        logger.error(f"Error for user {user_id}: {str(e)}")
        error = str(e).lower()
        if any(word in error for word in ["private", "unavailable", "login"]):
            await status.edit_text("❌ Это видео/фото приватное или недоступно.")
        elif "instagram" in error:
            await status.edit_text("❌ Instagram заблокировал скачивание. Попробуйте позже.")
        else:
            await status.edit_text("❌ Не удалось скачать. Попробуйте другую ссылку.")

    finally:
        cleanup_folder(user_folder)


# ========================= RUN =========================
async def main():
    logger.info("🚀 SaveReelBot запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())