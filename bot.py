import asyncio
import logging
import os
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# ========================= НАСТРОЙКИ =========================
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = "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"

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
Ты — мудрый и empathetic толкователь снов. 
Отвечай интересно, но не длинно (6-8 предложений).
Эмодзи используй умеренно.
"""

user_data = {}   # {chat_id: {"mode": "...", "history": [...] }}

# Принудительное логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logger.info("🚀 Бот начал запуск...")

client = Groq(api_key=GROQ_API_KEY)


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
    logger.info(f"Сообщение от {chat_id}: {text[:100]}...")

    await update.message.chat.send_action("typing")

    try:
        if user_data.get(chat_id, {}).get("mode") == "waiting" or chat_id not in user_data:
            # Новый сон
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

            user_data[chat_id] = {
                "mode": "dream_mode",
                "history": messages + [{"role": "assistant", "content": answer}]
            }

            await update.message.reply_text(
                answer + "\n\n"
                "Теперь можешь задавать вопросы по этому сну.\n"
                "/new — начать новый сон"
            )

        else:
            # Продолжение чата
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

        logger.info("Ответ отправлен успешно")

    except Exception as e:
        logger.error(f"ОШИБКА: {e}", exc_info=True)
        await update.message.reply_text("😔 Слишком много запросов. Подожди 10 секунд и попробуй снова.")


async def new_dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    await update.message.reply_text("🆕 Новый сон активирован! Расскажи, что приснилось ✨")


def main():
    logger.info("Запуск Application...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_dream))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот успешно запущен и ожидает сообщений!")
    app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())