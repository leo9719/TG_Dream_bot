def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # ==================== ОБРАБОТЧИКИ ====================
    conv_analyze = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_dream_start)],
        states={
            WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dream_description)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="analyze_conv",
        persistent=False,
    )

    conv_interpret = ConversationHandler(
        entry_points=[CommandHandler("interpret", interpret_symbol_start)],
        states={
            WAITING_FOR_DREAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_symbol_for_interpretation)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="interpret_conv",
        persistent=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_analyze)
    app.add_handler(conv_interpret)
    app.add_handler(CommandHandler("stats", lambda u, c: u.message.reply_text("📊 Статистика пока в разработке.")))
    app.add_handler(CommandHandler("cancel", cancel))

    # Добавляем обработчик всех текстовых сообщений как fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    logger.info("Бот запущен и готов к работе...")
    app.run_polling(drop_pending_updates=True)