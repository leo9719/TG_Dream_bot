import os
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN = os.getenv(BOT_TOKEN)

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = downloads
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message Message)
    await message.answer(Привет! Отправь ссылку на видео (TikTok  YouTube  Instagram  Shorts))


def download_video(url str)
    ydl_opts = {
        outtmpl f{DOWNLOAD_DIR}%(title)s.%(ext)s,
        format best[ext=mp4]best,           # ← главное изменение
        noplaylist True,
        quiet True,
        no_warnings True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

    # Простая попытка исправить растяжение (если ffmpeg есть)
    try
        fixed_path = str(Path(file_path).with_name(Path(file_path).stem + _fixed.mp4))
        import subprocess
        subprocess.run([
            ffmpeg, -y, -i, file_path,
            -c, copy, -metadatasv0, rotate=0,
            fixed_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        
        if os.path.exists(fixed_path) and os.path.getsize(fixed_path)  10000
            os.remove(file_path)
            return fixed_path
    except
        pass

    return file_path


@dp.message(F.text)
async def downloader(message Message)
    url = message.text.strip()
    if not url.startswith(http)
        return await message.answer(Отправь нормальную ссылку на видео.)

    wait = await message.answer(Скачиваю видео... ⏳)

    try
        file_path = await asyncio.to_thread(download_video, url)
        
        await message.answer_video(
            FSInputFile(file_path),
            supports_streaming=True
        )
        
        await wait.delete()

        # Очистка
        for f in [file_path]
            try
                if os.path.exists(f)
                    os.remove(f)
            except
                pass

    except Exception as e
        await wait.edit_text(fОшибка {str(e)[250]})


async def main()
    print(Bot started ✅)
    await dp.start_polling(bot)


if __name__ == __main__
    asyncio.run(main())