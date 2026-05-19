import os
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

# ←←← ИЗМЕНИ НА СВОЙ ДОМЕН ОТ BOTHOST ←←←
WEBHOOK_HOST = "https://твой-проект.bothost.ru"   # ← сюда свой URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Отправь ссылку на видео\n"
        "(TikTok / YouTube / Instagram / Shorts)"
    )


def download_video(url: str):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        # Проверка реального файла после merge
        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            filename = base + ".mp4"

    # === Фикс растяжения видео ===
    try:
        fixed_path = str(Path(filename).with_name(Path(filename).stem + "_fixed.mp4"))
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-i", filename,
            "-c", "copy",
            "-metadata:s:v:0", "rotate=0"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

        if os.path.exists(fixed_path):
            os.remove(filename)
            return fixed_path
    except:
        pass  # ffmpeg нет — отправляем как есть

    return filename


@dp.message(F.text)
async def downloader(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.answer("Отправь нормальную ссылку на видео.")

    wait = await message.answer("Скачиваю видео... ⏳")

    try:
        file_path = await asyncio.to_thread(download_video, url)

        await message.answer_video(
            FSInputFile(file_path),
            supports_streaming=True
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


async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    print("Bot stopped")


if __name__ == "__main__":
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    print("🚀 Bot started with webhook")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))