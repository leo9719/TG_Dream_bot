import os
import asyncio
import subprocess
import tempfile
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
    await message.answer(
        "Привет! Отправь ссылку на видео "
        "(TikTok / YouTube / Instagram / Shorts)"
    )


def download_video(url: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            "noplaylist": True,
            "quiet": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = Path(ydl.prepare_filename(info))

        final_file = Path(DOWNLOAD_DIR) / f"{downloaded_file.stem}_fixed.mp4"

        # Исправляем растяжение видео
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(downloaded_file),
                "-c", "copy",
                "-metadata:s:v:0", "rotate=0",
                "-aspect", "auto",
                str(final_file)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            return str(final_file)
        except Exception:
            # Если ffmpeg не найден — отправляем как есть
            print("FFmpeg не найден, отправляем оригинал")
            return str(downloaded_file)


@dp.message(F.text)
async def downloader(message: Message):
    url = message.text.strip()

    if not url.startswith("http"):
        await message.answer("Отправь нормальную ссылку на видео.")
        return

    wait_message = await message.answer("Скачиваю видео... ⏳")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        video = FSInputFile(file_path)

        await message.answer_video(video, supports_streaming=True)

        # Очистка
        for f in [file_path, str(Path(file_path).with_suffix(''))]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass

        await wait_message.delete()

    except Exception as e:
        await wait_message.edit_text(f"Ошибка: {str(e)}")


async def main():
    print("Bot started ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())