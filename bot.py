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
from nlp_utils import extract_keywords

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_DREAM = 1

# Инициализация БД
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот для анализа снов.\n"
        "Доступные команды:\n"
        "/analyze - проанализировать сон\n"
        "/interpret - интерпретация символа\n"
        "Просто нажми /analyze и опиши свой сон, когда я попрошу."
    )

async def analyze_dream_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс анализа сна"""
    await update.message.reply_text("💭 Пожалуйста, опиши свой сон как можно подробнее:")
    return WAITING_FOR_DREAM

async def receive_dream_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает описание сна и обрабатывает его"""
    dream_text = update.message.text
    user_id = update.effective_user.id
    
    try:
        symbols = extract_keywords(dream_text, top_n=5)
        
        if not symbols:
            await update.message.reply_text("Не нашёл значимых символов в описании сна. Попробуй описать подробнее.")
            return ConversationHandler.END
        
        response = "🔍 Результаты анализа сна:\n\n"
        found_interpretations = False
        
        for symbol in symbols:
            try:
                cached = get_cached_interpretation(symbol)
                
                if cached:
                    interpretation = cached
                else:
                    interpretation = parse_dream_symbol(symbol)
                    if interpretation and interpretation != "Интерпретация не найдена.":
                        save_interpretation(user_id, symbol, interpretation)
                
                if interpretation and interpretation != "Интерпретация не найдена.":
                    response += f"🔮 {symbol.capitalize()}:\n{interpretation}\n\n"
                    found_interpretations = True
            
            except Exception as e:
                logger.error(f"Ошибка обработки символа {symbol}: {e}")
                continue
        
        if not found_interpretations:
            response = "К сожалению, не удалось найти интерпретаций для символов в вашем сне."
        
        await update.message.reply_text(response[:4000])
    
    except Exception as e:
        logger.error(f"Ошибка анализа сна: {e}")
        await update.message.reply_text("Произошла ошибка при анализе сна. Пожалуйста, попробуй позже.")
    
    return ConversationHandler.END

async def interpret_symbol_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс интерпретации символа"""
    await update.message.reply_text("🔮 Какой символ из сна ты хочешь интерпретировать?")
    return WAITING_FOR_DREAM

async def receive_symbol_for_interpretation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает символ для интерпретации"""
    symbol = update.message.text
    try:
        interpretation = parse_dream_symbol(symbol)
        await update.message.reply_text(f"🔮 {symbol.capitalize()}:\n{interpretation}")
    except Exception as e:
        logger.error(f"Ошибка интерпретации символа {symbol}: {e}")
        await update.message.reply_text("Произошла ошибка при поиске интерпретации. Пожалуйста, попробуй позже.")
    
    return ConversationHandler.END

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    await update.message.reply_text(
        "📊 Статистика снов:\n"
        "Всего проанализировано: 10 снов\n"
        "Частые символы: вода (3), змея (2), полёт (2)\n"
        "Преобладающий тон: нейтральный (60%)"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущую операцию"""
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # Обработчик для анализа сна
    conv_handler_analyze = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_dream_start)],
        states={
            WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dream_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Обработчик для интерпретации символа
    conv_handler_interpret = ConversationHandler(
        entry_points=[CommandHandler("interpret", interpret_symbol_start)],
        states={
            WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_symbol_for_interpretation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler_analyze)
    app.add_handler(conv_handler_interpret)
    app.add_handler(CommandHandler("stats", show_stats))
    
    # Запуск бота
    app.run_polling()
    logger.info("Бот запущен")

if __name__ == "__main__":
    main()