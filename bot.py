# -*- coding: utf-8 -*-
import os
import re
import time
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# ========================= CONFIG =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

MAX_VIDEO_SIZE = 400 * 1024 * 1024   # 400 МБ
MAX_DURATION = 25 * 60
COOLDOWN_SECONDS = 6
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

# ========================= BOT =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

user_stats = {}
user_cooldowns = {}
user_last_activity = {}

# ========================= AUTO UPDATE yt-dlp =========================
def update_ytdlp():
    try:
        logger.info("🔄 Обновляем yt-dlp...")
        result = subprocess.run(["pip", "install", "--upgrade", "yt-dlp"], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            logger.info("✅ yt-dlp успешно обновлён")
        else:
            logger.warning("⚠️ Не удалось обновить yt-dlp")
    except Exception as e:
        logger.error(f"Ошибка обновления yt-dlp: {e}")

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
async def download_media(url: str, output_dir: Path, status_message: Message, is_audio: bool = False):
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        percent = float(d.get('_percent_str', '0').strip('%'))
                        asyncio.create_task(status_message.edit_text(f"⬇️ Скачиваю... {percent:.1f}% (попытка {attempt})"))
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
            logger.warning(f"Попытка {attempt}/{MAX_DOWNLOAD_ATTEMPTS} failed: {e}")
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(3)
            else:
                raise

# ========================= MENU =========================
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📥 Как пользоваться", callback_data="help")],
    [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats")],
])

# ========================= HANDLERS =========================
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>Добро пожаловать в SaveReelBot!</b>\n\n"
        "Отправь ссылку на видео или пост из Instagram, TikTok или YouTube.\n"
        "Поддерживаются Reels, Stories, Highlights, карусели и аудио.",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "📋 <b>Как пользоваться:</b>\n\n"
        "• Просто отправь ссылку\n"
        "• Бот автоматически определит тип контента\n"
        "• Лимит — 30 файлов в сутки\n"
        "• Cookies Instagram улучшают скачивание приватных постов",
        parse_mode="HTML"
    )

@dp.message(Command("stats"))
async def stats(message: Message):
    user_id = message.from_user.id
    count = user_stats.get(user_id, {}).get("count", 0)
    await message.answer(f"📊 Скачано сегодня: <b>{count}</b> / {DAILY_LIMIT}", parse_mode="HTML")

# ========================= MAIN =========================
@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        return await message.answer("⏳ Слишком часто. Подожди немного.")
    if not check_daily_limit(user_id):
        return await message.answer("⛔️ Дневной лимит (30) исчерпан.")

    if not is_allowed_url(url):
        return await message.answer("❌ Поддерживаются только Instagram, TikTok, YouTube.")

    status = await message.answer("⏳ Проверяю ссылку...")

    user_folder = get_user_folder(user_id)

    try:
        is_audio = any(x in url.lower() for x in ["music", "audio", "mp3", "song", "песня", "музыка"])

        file_path = await download_media(url, user_folder, status, is_audio)

        user_stats[user_id]["count"] += 1

        if file_path.endswith('.mp3'):
            await message.answer_audio(FSInputFile(file_path), caption="✅ Готово!")
        else:
            await message.answer_document(FSInputFile(file_path), caption="✅ Готово!")

        await status.delete()

    except Exception as e:
        logger.error(f"User {user_id} error: {e}")
        await status.edit_text("❌ Не удалось скачать. Попробуй другую ссылку.")

    finally:
        cleanup_folder(user_folder)

async def main():
    update_ytdlp()
    check_cookies()
    logger.info("🚀 SaveReelBot запущен (улучшенная версия)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())