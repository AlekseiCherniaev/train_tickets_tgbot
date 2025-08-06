import structlog
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    Application,
)

from app.handlers import start, enter_ticket_data, cancel, add_ticket
from app.task_manager import task_manager

logger = structlog.getLogger("ticket_bot")


class TicketBot:
    def __init__(self, token: str) -> None:
        self.token = token

    def start_bot(self) -> None:
        logger.info("Starting bot")
        self.application = ApplicationBuilder().token(self.token).build()
        self.add_handlers()
        self.application.post_stop = self.shutdown
        logger.info("Startup complete")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def add_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", start))
        self.application.add_handler(
            MessageHandler(
                filters.TEXT
                & ~filters.COMMAND
                & ~filters.Regex(r"^(Отмена|отмена)$")
                & ~filters.Regex(r"^(Ещё один билет|eщё один билет)$"),
                enter_ticket_data,
            )
        )
        self.application.add_handler(
            MessageHandler(filters.Regex(r"^(Отмена|отмена)$"), cancel)
        )
        self.application.add_handler(
            MessageHandler(
                filters.Regex(r"^(Ещё один билет|eщё один билет)$"), add_ticket
            )
        )
        logger.info("All handlers added")

    async def shutdown(self, application: Application) -> None:  # type: ignore
        logger.info("Stopping bot")
        active_users = task_manager.get_active_users()
        for user_id in active_users:
            try:
                await application.bot.send_message(
                    user_id,
                    "⚠️ Бот будет остановлен. Все активные поиски прекращены.",
                    reply_markup=ReplyKeyboardRemove(),
                )
            except Exception as e:
                logger.warning(f"Failed to notify user {user_id}: {e}")
        await task_manager.cancel_all_tasks()
        logger.info("Shutdown complete")
