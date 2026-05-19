import asyncio
import logging
import os
import sys
from random import uniform

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI, APIError, RateLimitError

# ========================= НАСТРОЙКИ =========================
TOKEN = os.getenv("TOKEN")
DEEPSEEK_API_KEY = "sk-02d861ee80d649efa40e69d0e771b4fc"   # ← ТВОЙ НОВЫЙ КЛЮЧ

MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = """
Ты — мудрый и empathetic толкователь снов. 
Отвечай интересно, но не длинно (5-8 предложений).
Эмодзи используй умеренно.
"""

user_data = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.info("🚀 Бот запускается с новым ключом...")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


async def call_deepseek_with_retry(messages, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.75,
                max_tokens=700,
                timeout=30
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            wait = (2 ** attempt) * 2.5 + uniform(0.5, 2.5)
            logger.warning(f"Rate limit → ждём {wait:.1f}с")
            await asyncio.sleep(wait)
        except APIError as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                wait = (2 ** attempt) * 3
                logger.warning(f"429 → ждём {wait}с")
                await asyncio.sleep(wait)
            else:
                logger.error(f"API Error: {e}")
                await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Не удалось получить ответ")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    await update.message.reply_text(
        "👋 Привет! Я толкователь снов.\n\n"
        "Расскажи свой сон подробно ✨\n"
        "После толкования можешь задавать вопросы."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    logger.info(f"📨 Сообщение от {chat_id}")

    await update.message.chat.send_action("typing")

    try:
        if user_data.get(chat_id, {}).get("mode") == "waiting" or chat_id not in user_data:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Расскажи сон: {text}"}
            ]
            is_new = True
        else:
            user_data[chat_id]["history"].append({"role": "user", "content": text})
            messages = user_data[chat_id]["history"]
            is_new = False

        answer = await call_deepseek_with_retry(messages)

        if is_new:
            user_data[chat_id] = {
                "mode": "dream_mode",
                "history": messages + [{"role": "assistant", "content": answer}]
            }
            reply = answer + "\n\nТеперь можешь задавать вопросы по этому сну.\n/new — новый сон"
        else:
            user_data[chat_id]["history"].append({"role": "assistant", "content": answer})
            reply = answer

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("⏳ DeepSeek сейчас загружен. Подожди 15–25 секунд и попробуй снова.")


async def new_dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"mode": "waiting", "history": []}
    await update.message.reply_text("🆕 Новый сон! Расскажи, что приснилось ✨")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_dream))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот успешно запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())