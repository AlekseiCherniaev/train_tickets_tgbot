import structlog

from app.bot import TicketBot
from app.logger import prepare_logger
from app.settings import settings

logger = structlog.get_logger("app")


def main() -> None:
    prepare_logger(settings.log_level)
    ticket_bot = TicketBot(token=settings.bot_token)
    ticket_bot.start_bot()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped via keyboard interrupt")
