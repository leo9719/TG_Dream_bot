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
    raise ValueError("BOT_TOKEN not found")

MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DURATION = 10 * 60             # 10 minutes
COOLDOWN_SECONDS = 10
MAX_CONCURRENT_DOWNLOADS = 3

ALLOWED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
}

# =========================
# BOT
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

download_semaphore = asyncio.Semaphore(
    MAX_CONCURRENT_DOWNLOADS
)

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

        return host in ALLOWED_DOMAINS

    except Exception:
        return False


def check_rate_limit(user_id: int) -> bool:
    now = time.time()

    last_request = user_cooldowns.get(user_id)

    if last_request:
        if now - last_request < COOLDOWN_SECONDS:
            return False

    user_cooldowns[user_id] = now
    return True


def sanitize_folder_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_-]", "", value)


def get_user_folder(user_id: int) -> Path:
    folder = BASE_DOWNLOAD_DIR / sanitize_folder_name(
        str(user_id)
    )

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
    }) as ydl:

        info = ydl.extract_info(
            url,
            download=False
        )

        duration = info.get("duration")

        if duration and duration > MAX_DURATION:
            raise ValueError(
                "Video duration exceeds limit."
            )

        size = (
            info.get("filesize")
            or info.get("filesize_approx")
        )

        if size and size > MAX_VIDEO_SIZE:
            raise ValueError(
                "Video size exceeds limit."
            )

        return info


def download_video(url: str, output_dir: Path):

    ydl_opts = {
        "outtmpl": str(
            output_dir / "%(title)s.%(ext)s"
        ),

        # без ffmpeg
        "format": "best",

        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        # защита от бесконечных ретраев
        "retries": 2,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

        filename = ydl.prepare_filename(info)

        return filename


# =========================
# COMMANDS
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "📥 Отправь ссылку на TikTok, "
        "YouTube или Instagram."
    )


# =========================
# MAIN HANDLER
# =========================

@dp.message(F.text)
async def handle_url(message: Message):

    user_id = message.from_user.id
    url = message.text.strip()

    if not check_rate_limit(user_id):
        await message.answer(
            "⏳ Подожди немного перед следующим запросом."
        )
        return

    if not is_allowed_url(url):
        await message.answer(
            "❌ Поддерживаются только "
            "TikTok, YouTube и Instagram."
        )
        return

    status = await message.answer(
        "⏳ Проверяю видео..."
    )

    user_folder = get_user_folder(user_id)

    try:

        validate_media(url)

        await status.edit_text(
            "⬇️ Скачиваю..."
        )

        async with download_semaphore:

            file_path = await asyncio.to_thread(
                download_video,
                url,
                user_folder
            )

        if not os.path.exists(file_path):
            raise RuntimeError(
                "Downloaded file not found."
            )

        file_size = os.path.getsize(file_path)

        if file_size > MAX_VIDEO_SIZE:
            raise RuntimeError(
                "File too large."
            )

        await status.edit_text(
            "📤 Отправляю..."
        )

        video = FSInputFile(file_path)

        await message.answer_video(
            video=video,
            caption="✅ Готово"
        )

        await status.delete()

    except ValueError as e:

        text = str(e)

        if "duration" in text:
            await status.edit_text(
                "❌ Видео длиннее 10 минут."
            )

        elif "size" in text:
            await status.edit_text(
                "❌ Видео слишком большое."
            )

        else:
            await status.edit_text(
                "❌ Невозможно обработать видео."
            )

    except Exception:

        # не показываем пользователю
        # внутренние ошибки

        await status.edit_text(
            "❌ Не удалось скачать видео."
        )

    finally:

        cleanup_folder(user_folder)


# =========================
# RUN
# =========================

async def main():
    print("Bot started ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())