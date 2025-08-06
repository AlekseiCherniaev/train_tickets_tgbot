import structlog
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    Application,
)

from app.handlers import start, enter_ticket_data

logger = structlog.getLogger("ticket_bot")


class TicketBot:
    def __init__(self, token: str) -> None:
        self.token = token

    def start_bot(self) -> None:
        logger.info("Starting bot")
        application = ApplicationBuilder().token(self.token).build()
        TicketBot.add_handlers(application)
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    @staticmethod
    def add_handlers(application: Application) -> None:  # type: ignore
        application.add_handler(CommandHandler("start", start))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ticket_data)
        )
        logger.info("All handlers added")
