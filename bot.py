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
        
        # Самый надёжный вариант без слияния форматов
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        
        # Защита от merge
        "merge_output_format": None,
        "postprocessors": [],
        
        # Дополнительные настройки для совместимости
        "prefer_free_formats": True,
        "format_sort": ["ext:mp4", "vcodec:h264", "res"],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        # Ищем подходящий файл
        base = os.path.splitext(filename)[0]
        for ext in [".mp4", ".webm", ".mkv", ""]:
            candidate = base + ext
            if os.path.exists(candidate):
                return candidate

        raise Exception("Файл не найден после скачивания")


@dp.message(F.text)
async def downloader(message: Message):
    url = message.text.strip()

    if not url.startswith("http"):
        await message.answer("Отправь нормальную ссылку.")
        return

    wait_message = await message.answer("Скачиваю видео... ⏳")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        if not os.path.exists(file_path):
            raise Exception("Файл не скачался")

        video = FSInputFile(file_path)

        await message.answer_video(
            video,
            caption="✅ Готово!"
        )

        try:
            os.remove(file_path)
        except:
            pass

        await wait_message.delete()

    except Exception as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() or "merging" in error_msg.lower():
            error_msg = "Сервер не поддерживает ffmpeg. Попробуй позже."
        await wait_message.edit_text(f"❌ Ошибка: {error_msg}")


async def main():
    print("Bot started ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())