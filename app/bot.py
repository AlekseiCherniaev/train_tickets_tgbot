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
    CANCEL_KEYWORDS = r"^(Отмена|отмена)$"
    ADD_TICKET_KEYWORDS = r"^(Ещё один билет|eщё один билет)$"
    TEXT_FILTER = (
        filters.TEXT
        & ~filters.COMMAND
        & ~filters.Regex(CANCEL_KEYWORDS)
        & ~filters.Regex(ADD_TICKET_KEYWORDS)
    )

    def __init__(self, token: str) -> None:
        self.token = token
        self.application: Application | None = None  # type: ignore

    def start_bot(self) -> None:
        """Main entry point for starting the bot."""
        logger.info("Starting bot")
        self.application = (
            ApplicationBuilder().token(self.token).post_stop(self.shutdown).build()
        )
        self.add_handlers()
        # self.application.post_stop = self.shutdown
        logger.info("Startup complete")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def add_handlers(self) -> None:
        """Register all handlers with the application."""
        if not self.application:
            raise ValueError("Application not initialized. Call start_bot() first.")
        handlers = [
            CommandHandler("start", start),
            MessageHandler(self.TEXT_FILTER, enter_ticket_data),
            MessageHandler(filters.Regex(self.CANCEL_KEYWORDS), cancel),
            MessageHandler(filters.Regex(self.ADD_TICKET_KEYWORDS), add_ticket),
        ]

        for handler in handlers:
            self.application.add_handler(handler)
        logger.info("All handlers added")

    @staticmethod
    async def shutdown(application: Application) -> None:  # type: ignore
        """Cleanup tasks during bot shutdown."""
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
