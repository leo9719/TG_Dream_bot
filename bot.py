import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN not specified")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "📥 Отправь ссылку на TikTok, YouTube или Instagram"
    )


def download_video(url: str):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": "best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


@dp.message(F.text)
async def download_handler(message: Message):
    url = message.text.strip()

    if not url.startswith("http"):
        await message.answer("❌ Отправь корректную ссылку.")
        return

    status = await message.answer("⏳ Скачиваю видео...")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        if not os.path.exists(file_path):
            await status.edit_text("❌ Файл не найден.")
            return

        video = FSInputFile(file_path)

        await message.answer_video(
            video=video,
            caption="✅ Готово"
        )

        try:
            os.remove(file_path)
        except Exception:
            pass

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Ошибка:\n{e}")


async def main():
    print("Bot started ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())