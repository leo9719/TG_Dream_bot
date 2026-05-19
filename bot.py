import os
import asyncio
import subprocess
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Привет! Отправь ссылку на видео (TikTok / YouTube / Instagram / Shorts)")


def download_video(url: str):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",  # как в лучших ботах
        "noplaylist": True,
        "quiet": True,
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = Path(ydl.prepare_filename(info))

    # === ИСПРАВЛЕНИЕ РАСТЯЖЕНИЯ ===
    fixed_path = file_path.with_name(file_path.stem + "_fixed.mp4")

    try:
        # Сбрасываем rotate и aspect ratio (самый частый фикс)
        subprocess.run([
            "ffmpeg", "-y", "-i", str(file_path),
            "-c", "copy",
            "-metadata:s:v:0", "rotate=0",
            "-aspect", "16:9",          # можно убрать, если вертикальное
            str(fixed_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

        if fixed_path.exists() and fixed_path.stat().st_size > 10000:
            file_path.unlink(missing_ok=True)
            return str(fixed_path)
    except:
        pass  # ffmpeg не обязателен

    return str(file_path)


@dp.message(F.text)
async def downloader(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.answer("Нужна ссылка на видео.")

    wait = await message.answer("Скачиваю... ⏳")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        video = FSInputFile(file_path)

        await message.answer_video(
            video,
            supports_streaming=True,
            # width=1080, height=1920  # можно добавить, если хочешь
        )

        await wait.delete()

        # Очистка
        for f in [file_path]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass

    except Exception as e:
        await wait.edit_text(f"Ошибка: {str(e)[:200]}")


async def main():
    print("Bot started ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())