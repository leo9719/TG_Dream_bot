import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Принудительное логирование
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

TOKEN = "ТОКЕН_ЗДЕСЬ"   # ← ВСТАВЬ СВОЙ ТЕЛЕГРАМ ТОКЕН

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /start получена")
    await update.message.reply_text("Бот работает! Напиши любой текст.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получено сообщение: {update.message.text}")
    await update.message.reply_text("Я получил: " + update.message.text)

def main():
    logger.info("=== БОТ НАЧИНАЕТ ЗАПУСК ===")
    print("=== PRINT: БОТ ЗАПУСКАЕТСЯ ===")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("=== БОТ УСПЕШНО ЗАПУЩЕН ===")
    print("=== PRINT: БОТ ЗАПУЩЕН УСПЕШНО ===")
    
    app.run_polling()

if __name__ == "__main__":
    main()