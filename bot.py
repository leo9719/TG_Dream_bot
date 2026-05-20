import os
import asyncio
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
        "(TikTok / YouTube / Instagram)"
    )


def download_video(url: str):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": "best",
        "noplaylist": True,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        base = os.path.splitext(filename)[0]
        mp4_file = base + ".mp4"

        if os.path.exists(mp4_file):
            filename = mp4_file

        return filename


@dp.message(F.text)
async def downloader(message: Message):
    url = message.text.strip()

    if not url.startswith("http"):
        await message.answer("Отправь нормальную ссылку.")
        return

    wait_message = await message.answer("Скачиваю видео...")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        video = FSInputFile(file_path)

        await message.answer_video(video)

        try:
            os.remove(file_path)
        except:
            pass

        await wait_message.delete()

    except Exception as e:
        await wait_message.edit_text(f"Ошибка: {e}")


async def main():
    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())