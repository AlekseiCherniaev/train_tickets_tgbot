import os

import structlog
from dotenv import load_dotenv

from app.bot import TicketBot
from app.logger import prepare_logger

logger = structlog.get_logger("app")


def main() -> None:
    prepare_logger(os.getenv("LOG_LEVEL", "INFO"))
    load_dotenv()
    if os.getenv("BOT_TOKEN") is None:
        raise ValueError(
            "BOT_TOKEN is not set. Please set it in the .env file or as an environment variable"
        )
    ticket_bot = TicketBot(token=os.getenv("BOT_TOKEN"))  # type: ignore
    ticket_bot.start_bot()


if __name__ == "__main__":
    main()
