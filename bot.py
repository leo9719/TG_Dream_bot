#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import config
from parser import parse_dream_symbol
from db_utils import init_db, save_interpretation, get_cached_interpretation
import logging
from nlp_utils import extract_keywords, load_spacy

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
WAITING_FOR_DREAM = 1

# Инициализация БД
init_db()

# Предзагрузка модели spaCy при старте
load_spacy()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋 Я бот для анализа снов.\n\n"
        "Команды:\n"
        "/analyze — описать сон\n"
        "/interpret — интерпретировать символ\n"
        "/stats — статистика"
    )

async def analyze_dream_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💭 Опиши свой сон как можно подробнее:")
    return WAITING_FOR_DREAM

async def receive_dream_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dream_text = update.message.text
    user_id = update.effective_user.id
    
    try:
        symbols = extract_keywords(dream_text, top_n=5)
        
        if not symbols:
            await update.message.reply_text("Не удалось выделить символы. Попробуй описать сон подробнее.")
            return ConversationHandler.END

        response = "🔍 Анализ твоего сна:\n\n"
        found = False

        for symbol in symbols:
            try:
                cached = get_cached_interpretation(symbol)
                interpretation = cached if cached else parse_dream_symbol(symbol)
                
                if interpretation and interpretation != "Интерпретация не найдена.":
                    response += f"🔮 **{symbol.capitalize()}**:\n{interpretation}\n\n"
                    found = True
                    
                    if not cached:
                        save_interpretation(user_id, symbol, interpretation)
            except Exception as e:
                logger.error(f"Ошибка с символом {symbol}: {e}")
                continue

        if not found:
            response = "К сожалению, не нашёл интерпретаций для символов в этом сне."

        await update.message.reply_text(response[:4000])
    
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз позже.")

    return ConversationHandler.END

async def interpret_symbol_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 Введи символ, который хочешь интерпретировать:")
    return WAITING_FOR_DREAM

async def receive_symbol_for_interpretation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip()
    try:
        interpretation = parse_dream_symbol(symbol)
        await update.message.reply_text(f"🔮 **{symbol.capitalize()}**:\n{interpretation}")
    except Exception as e:
        logger.error(f"Ошибка интерпретации: {e}")
        await update.message.reply_text("Ошибка при получении интерпретации.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    conv_analyze = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_dream_start)],
        states={WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dream_description)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conv_interpret = ConversationHandler(
        entry_points=[CommandHandler("interpret", interpret_symbol_start)],
        states={WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_symbol_for_interpretation)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_analyze)
    app.add_handler(conv_interpret)
    app.add_handler(CommandHandler("stats", lambda u, c: u.message.reply_text("📊 Статистика пока в разработке.")))
    app.add_handler(CommandHandler("cancel", cancel))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()