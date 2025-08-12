import asyncio

import aiohttp
import structlog
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    Application,
)

from app.db.database_connection import PostgresDatabaseConnection
from app.db.ticket_request_repo import TicketRequestRepository
from app.handlers import start, enter_ticket_data, cancel, add_ticket
from app.settings import settings
from app.utils import make_get_request, calculate_retry_time

logger = structlog.get_logger(__name__)


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
        self.ticket_repo = TicketRequestRepository(
            PostgresDatabaseConnection(
                dbname=settings.postgres_db,
                dbuser=settings.postgres_user,
                dbpassword=settings.postgres_password,
                dbhost=settings.postgres_host,
                dbport=settings.postgres_port_external,
            )
        )

    def start_bot(self) -> None:
        """Main entry point for starting the bot."""
        logger.info("Starting bot...")
        self.ticket_repo.create_table()
        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .post_init(self.background_task)
            .post_stop(self.shutdown)
            .build()
        )
        self.application.bot_data["ticket_repo"] = self.ticket_repo
        self.add_handlers()
        logger.info("Startup complete")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    @staticmethod
    async def background_task(application: Application) -> None:  # type: ignore
        asyncio.create_task(TicketBot.check_ticket_availability(application))

    @staticmethod
    async def check_ticket_availability(application: Application) -> None:  # type: ignore
        while True:
            logger.info("Checking ticket availability...")
            unique_requests = {
                (
                    request["departure_station"],
                    request["arrival_station"],
                    request["travel_date"],
                    request["travel_time"],
                )
                for request in application.bot_data["ticket_repo"].get_active_requests()
            }

            async with aiohttp.ClientSession() as session:
                try:
                    for request_data in unique_requests:
                        url = f"https://pass.rw.by/ru/route/?from={request_data[0]}&to={request_data[1]}&date={request_data[2]}"
                        response = await make_get_request(url=url, session=session)
                        if response.status != 200:
                            raise Exception(f"HTTP error {response.status}")

                        soup = BeautifulSoup(await response.text(), "html.parser")
                        target_block = soup.find(
                            "div",
                            class_="sch-table__time train-from-time",
                            string=str(request_data[3].strftime("%H:%M")),
                        )
                        if not target_block or (
                            (
                                train_block := target_block.find_parent(
                                    "div", class_="sch-table__row"
                                )
                            )
                            is None
                        ):
                            logger.bind(url=url, params=request_data).error(
                                "Target block not found, wrong train parameters"
                            )
                            active_chats = application.bot_data[
                                "ticket_repo"
                            ].get_chats_by_ticket_params(
                                departure=request_data[0],
                                arrival=request_data[1],
                                date=request_data[2],
                                time=request_data[3],
                            )
                            for chat_id in active_chats:
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"❌ Ошибка при проверке билетов {request_data[0]} → {request_data[1]} "
                                    f"Неверно указаны станции или время"
                                    f"Попробуйте снова",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [["Отмена"]],
                                        resize_keyboard=True,
                                        one_time_keyboard=True,
                                    ),
                                )
                            application.bot_data["ticket_repo"].set_request_inactive(
                                departure=request_data[0],
                                arrival=request_data[1],
                                date=request_data[2],
                                time=request_data[3],
                                chat_id=chat_id,
                            )
                            await asyncio.sleep(calculate_retry_time(1))
                            continue

                        ticket_available = (
                            train_block.get("data-ticket_selling_allowed", "").lower()  # type: ignore
                            == "true"
                        )

                        if ticket_available:
                            active_chats = application.bot_data[
                                "ticket_repo"
                            ].get_chats_by_ticket_params(
                                departure=request_data[0],
                                arrival=request_data[1],
                                date=request_data[2],
                                time=request_data[3],
                            )
                            for chat_id in active_chats:
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"✅ Билет появился в продаже! {request_data[0]} → {request_data[1]} {request_data[2]} {request_data[3]}",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [["Отмена"]],
                                        resize_keyboard=True,
                                        one_time_keyboard=True,
                                    ),
                                )
                            logger.bind(url=url, params=request_data).info(
                                "Tickets found"
                            )
                        else:
                            logger.bind(
                                url=url, chat_id=chat_id, params=request_data
                            ).debug("No tickets found")
                        await asyncio.sleep(calculate_retry_time(1))

                    await asyncio.sleep(calculate_retry_time())

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.bind(url=url, error=str(e)).error(
                        f"Ticket checking failed after retries: {settings.retry_attempts}"
                    )
                except Exception as e:
                    logger.bind(url=url, error=str(e)).error("Ticket checking error")

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
        logger.info("Shutdown complete")
