import os
import re
import time
import shutil
import asyncio
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
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
# ====================================================

ALLOWED_DOMAINS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
}

# ========================= BOT =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

COOKIES_FILE = "cookies.txt"   # ← положи сюда файл cookies для Instagram (опционально)

# ========================= HELPERS =========================
def is_allowed_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in ALLOWED_DOMAINS)
    except:
        return False


def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    if not hasattr(check_rate_limit, "last_request"):
        check_rate_limit.last_request = {}
    if user_id in check_rate_limit.last_request and now - check_rate_limit.last_request[user_id] < COOLDOWN_SECONDS:
        return False
    check_rate_limit.last_request[user_id] = now
    return True


def get_user_folder(user_id: int) -> Path:
    folder = BASE_DOWNLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_folder(folder: Path):
    shutil.rmtree(folder, ignore_errors=True)


def download_video(url: str, output_dir: Path):
    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "format": "bestvideo[height<=1080][filesize<400M]/best[height<=1080]/best",  # Максимальное качество
        "noplaylist": True,
        "quiet": False,
        "retries": 5,
        "socket_timeout": 40,
        "http_chunk_size": 10485760,
    }

    # Подключаем cookies, если файл существует (для приватных Instagram)
    if os.path.exists(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# ========================= HANDLERS =========================
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "📥 <b>SaveReelBot</b>\n\n"
        "Отправь ссылку на видео из Instagram, TikTok или YouTube.\n"
        "Бот скачает в максимальном доступном качестве.",
        parse_mode="HTML"
    )


@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        await message.answer("⏳ Подожди 8 секунд перед следующим запросом.")
        return

    if not is_allowed_url(url):
        await message.answer("❌ Поддерживаются только Instagram, TikTok и YouTube.")
        return

    status = await message.answer("⏳ Проверяю видео...")

    user_folder = get_user_folder(user_id)

    try:
        await status.edit_text("⬇️ Скачиваю в максимальном качестве...\nЭто может занять 10–40 секунд.")

        file_path = await asyncio.to_thread(download_video, url, user_folder)

        video = FSInputFile(file_path)
        await message.answer_video(
            video=video,
            caption="✅ Готово!\n@SaveReelBot",
            supports_streaming=True
        )

        await status.delete()

    except Exception as e:
        error = str(e).lower()
        if any(word in error for word in ["unavailable", "private", "not available", "login"]):
            await status.edit_text(
                "❌ Это видео недоступно для скачивания.\n"
                "Возможно, оно приватное или имеет возрастные ограничения."
            )
        elif "instagram" in error:
            await status.edit_text(
                "❌ Instagram заблокировал скачивание этого видео.\n"
                "Попробуй другую ссылку или повтори позже."
            )
        else:
            await status.edit_text("❌ Не удалось скачать видео. Попробуй другую ссылку.")

    finally:
        cleanup_folder(user_folder)


# ========================= RUN =========================
async def main():
    print("🚀 SaveReelBot успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())