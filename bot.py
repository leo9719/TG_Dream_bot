import asyncio
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# ========================= НАСТРОЙКИ =========================
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = "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"

MODEL = "llama-3.3-70b-versatile"   # Отличная модель на Groq

SYSTEM_PROMPT = """
Ты — мудрый, эмпатичный и глубокий толкователь снов.
Отвечай интересно, с душой, но не слишком длинно (6–8 предложений).
Используй эмодзи умеренно.
Если деталей мало — задай 1–2 уточняющих вопроса.
"""

# Хранилище данных пользователя
user_data = {}  # {chat_id: {"mode": "waiting"|"dream_mode", "history": [...] }}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}

    await update.message.reply_text(
        "👋 Привет! Я толкователь снов.\n\n"
        "Расскажи свой сон как можно подробнее, и я помогу его разобрать ✨\n"
        "После первого ответа можешь задавать любые вопросы по нему."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    if chat_id not in user_data:
        user_data[chat_id] = {"mode": "waiting", "history": []}

    await update.message.chat.send_action("typing")

    try:
        if user_data[chat_id]["mode"] == "waiting":
            # Первый сон
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Расскажи сон: {text}"}
            ]

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.75,
                max_tokens=800,
            )
            answer = response.choices[0].message.content

            user_data[chat_id]["history"] = messages + [{"role": "assistant", "content": answer}]
            user_data[chat_id]["mode"] = "dream_mode"

            await update.message.reply_text(
                answer + "\n\n"
                "Теперь можешь задавать любые уточняющие вопросы по этому сну.\n"
                "Чтобы начать новый сон — напиши /new"
            )

        else:
            # Продолжение разговора по сну
            user_data[chat_id]["history"].append({"role": "user", "content": text})

            response = client.chat.completions.create(
                model=MODEL,
                messages=user_data[chat_id]["history"],
                temperature=0.75,
                max_tokens=800,
            )
            answer = response.choices[0].message.content

            user_data[chat_id]["history"].append({"role": "assistant", "content": answer})

            await update.message.reply_text(answer)

    except Exception as e:
        logger.error(f"Ошибка Groq: {e}")
        await update.message.reply_text("😔 Сейчас слишком много запросов. Подожди 10–15 секунд и попробуй снова.")


async def new_dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    await update.message.reply_text("🆕 Новый сон! Расскажи, что тебе приснилось ✨")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_dream))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Бот-толкователь снов на Groq запущен!")
    app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())