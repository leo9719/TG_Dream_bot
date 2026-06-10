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

# ========================= LOGGING =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========================= LANGUAGES =========================
user_language = {}  # user_id → 'ru' or 'en'

TEXTS = {
    'ru': {
        'start': "👋 <b>Добро пожаловать в SaveReelBot!</b>\n\nВыберите язык:",
        'welcome': "Отправь ссылку на видео или фото.",
        'too_fast': "⏳ Подожди 6 секунд между запросами.",
        'limit_exceeded': "⛔️ Дневной лимит 30 скачиваний исчерпан.",
        'unsupported': "❌ Поддерживаются только Instagram, TikTok, YouTube.",
        'downloading': "⬇️ Скачиваю...",
        'done': "✅ Готово!",
        'error': "❌ Не удалось скачать. Попробуй другую ссылку."
    },
    'en': {
        'start': "👋 <b>Welcome to SaveReelBot!</b>\n\nChoose language:",
        'welcome': "Send a link to video or photo.",
        'too_fast': "⏳ Please wait 6 seconds between requests.",
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
        subprocess.run(["pip", "install", "--upgrade", "yt-dlp"], 
                      capture_output=True, text=True, timeout=60, check=True)
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
    return user_stats[user