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

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# ==================== ОГРАНИЧЕНИЯ ====================
MAX_VIDEO_SIZE = 300 * 1024 * 1024    # 300 МБ
MAX_DURATION = 20 * 60                # 20 минут
COOLDOWN_SECONDS = 8
MAX_CONCURRENT_DOWNLOADS = 3
# ====================================================

ALLOWED_DOMAINS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
}

# =========================
# BOT
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
user_cooldowns = {}

BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

# =========================
# HELPERS
# =========================

def is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.netloc.lower()
        return any(domain in host for domain in ALLOWED_DOMAINS)
    except Exception:
        return False


def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_SECONDS:
        return False
    user_cooldowns[user_id] = now
    return True


def sanitize_folder_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_-]", "", value)[:50] or "user"


def get_user_folder(user_id: int) -> Path:
    folder = BASE_DOWNLOAD_DIR / sanitize_folder_name(str(user_id))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_folder(folder: Path):
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass


def validate_media(url: str):
    with yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }) as ydl:
        info = ydl.extract_info(url, download=False)

        duration = info.get("duration")
        if duration and duration > MAX_DURATION:
            raise ValueError(f"duration:{duration}")

        size = info.get("filesize") or info.get("filesize_approx")
        if size and size > MAX_VIDEO_SIZE:
            raise ValueError(f"size:{size}")

        return info


def download_video(url: str, output_dir: Path):
    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "format": "best[height<=1080][filesize<300M]/best[height<=720]/best",
        "noplaylist": True,
        "quiet": False,           # для логов
        "no_warnings": True,
        "retries": 5,
        "socket_timeout": 30,
        "http_chunk_size": 10485760,  # 10MB chunks
        # Улучшения специально для Instagram / TikTok
        "extractor_args": {
            "instagram": {"login": False},
            "tiktok": {"api": "web"},
        },
        "postprocessors": [],  # можно добавить позже
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename


# =========================
# COMMANDS
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "📥 <b>SaveReelBot</b>\n\n"
        "Просто отправь ссылку на видео из Instagram, TikTok или YouTube.\n\n"
        "Поддержка: Reels • Shorts • TikTok • Фото + карусели",
        parse_mode="HTML"
    )


# =========================
# MAIN HANDLER
# =========================

@dp.message(F.text)
async def handle_url(message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        await message.answer("⏳ Подожди 8 секунд перед следующим запросом.")
        return

    if not is_allowed_url(url):
        await message.answer("❌ Поддерживаются только ссылки из Instagram, TikTok и YouTube.")
        return

    status = await message.answer("⏳ Проверяю видео...")

    user_folder = get_user_folder(user_id)

    try:
        validate_media(url)

        await status.edit_text("⬇️ Скачиваю... (это может занять 10–30 сек)")

        async with download_semaphore:
            file_path = await asyncio.to_thread(download_video, url, user_folder)

        if not os.path.exists(file_path):
            raise RuntimeError("File not found after download")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_VIDEO_SIZE:
            raise RuntimeError("File too large")

        await status.edit_text("📤 Отправляю в Telegram...")

        video = FSInputFile(file_path)
        await message.answer_video(
            video=video,
            caption="✅ Готово! @SaveReelBot",
            supports_streaming=True
        )

        await status.delete()

    except ValueError as e:
        error_str = str(e).lower()
        if "duration" in error_str:
            await status.edit_text("❌ Видео длиннее 20 минут.")
        elif "size" in error_str:
            await status.edit_text("❌ Видео слишком большое (> 300 МБ).")
        else:
            await status.edit_text("❌ Не удалось обработать это видео.")

    except Exception as e:
        error_str = str(e).lower()
        if "this content isn't available to everyone" in error_str or "private" in error_str or "login" in error_str:
            await status.edit_text(
                "❌ Это видео недоступно для скачивания.\n\n"
                "Причины:\n"
                "• Приватный аккаунт\n"
                "• Возрастное ограничение\n"
                "• Ограничение по региону"
            )
        elif "instagram" in error_str or "reel" in error_str:
            await status.edit_text(
                "❌ Instagram временно заблокировал это видео.\n"
                "Попробуй другую ссылку или повтори через 5–10 минут."
            )
        else:
            await status.edit_text("❌ Не удалось скачать видео. Попробуй другую ссылку.")

    finally:
        cleanup_folder(user_folder)


# =========================
# RUN
# =========================

async def main():
    print("🤖 SaveReelBot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())