import asyncio
import logging
import os
import sys
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI, APIError, RateLimitError

# ========================= НАСТРОЙКИ =========================
TOKEN = os.getenv("TOKEN")
DEEPSEEK_API_KEY = "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"

MODEL = "deepseek-v4-flash"   # ← Рекомендуемая сейчас модель

SYSTEM_PROMPT = """
Ты — мудрый и empathetic толкователь снов. 
Отвечай интересно, но не длинно (6-8 предложений).
Эмодзи используй умеренно.
"""

user_data = {}   # {chat_id: {"mode": "...", "history": [...] }}

# ==================== ЛОГИРОВАНИЕ ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.info("🚀 Бот запускается...")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    logger.info(f"Новый пользователь: {chat_id}")
    await update.message.reply_text(
        "👋 Привет! Я толкователь снов.\n\n"
        "Расскажи свой сон подробно ✨\n"
        "После толкования можешь задавать вопросы по нему."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    logger.info(f"📨 От {chat_id}: {text[:70]}...")

    await update.message.chat.send_action("typing")

    try:
        # Формируем сообщения
        if user_data.get(chat_id, {}).get("mode") == "waiting" or chat_id not in user_data:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Расскажи сон: {text}"}
            ]
            is_new_dream = True
        else:
            user_data[chat_id]["history"].append({"role": "user", "content": text})
            messages = user_data[chat_id]["history"]
            is_new_dream = False

        # Запрос к DeepSeek
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.75,
            max_tokens=700,
            timeout=30
        )

        answer = response.choices[0].message.content.strip()

        # Сохраняем историю
        if is_new_dream:
            user_data[chat_id] = {
                "mode": "dream_mode",
                "history": messages + [{"role": "assistant", "content": answer}]
            }
            reply_text = answer + "\n\nТеперь можешь задавать вопросы по этому сну.\n/new — новый сон"
        else:
            user_data[chat_id]["history"].append({"role": "assistant", "content": answer})
            reply_text = answer

        await update.message.reply_text(reply_text)

    except RateLimitError:
        logger.warning("Rate limit сработал")
        await update.message.reply_text(
            "⏳ Лимит запросов DeepSeek.\nПодожди 15–20 секунд и попробуй снова."
        )
    except APIError as e:
        logger.error(f"API Error: {e}")
        if "429" in str(e):
            await update.message.reply_text("⏳ Слишком много запросов. Подожди 20 секунд.")
        else:
            await update.message.reply_text("😔 Ошибка API. Попробуй через 10 секунд.")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}", exc_info=True)
        await update.message.reply_text("😔 Что-то пошло не так. Попробуй ещё раз через минуту.")


async def new_dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    await update.message.reply_text("🆕 Новый сон активирован! Расскажи, что приснилось ✨")


def main():
    logger.info("Запуск Telegram Bot...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_dream))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот успешно запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)