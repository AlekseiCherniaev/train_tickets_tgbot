import asyncio

import aiohttp
import structlog
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.constants import DATE_FORMAT, EXAMPLE_ROUTE
from app.db.ticket_request_repo import TicketRequestRepository
from app.settings import settings
from app.utils import (
    get_minsk_date,
    make_get_request,
    validate_time_input,
    validate_rzd_response,
    handle_invalid_input,
)

logger = structlog.get_logger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message with instructions."""
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
    message = (
        "🚂 <b>Поиск железнодорожных билетов</b>\n\n"
        "📝 <b>Введите данные в формате:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "📅 <b>Дата:</b> ГГГГ-ММ-ДД\n"
        "⏰ <b>Время:</b> ЧЧ:ММ (24-часовой формат)\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>{example}</code>\n\n"
    )
    await update.message.reply_html(message)
    logger.bind(
        user_id=user.id, username=user.username, chat_id=update.message.chat_id
    ).info(f"User {user.first_name} {user.last_name} started bot")


async def enter_ticket_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user input for ticket search."""
    if not update.message or not update.effective_user or not update.message.text:
        return None

    params = update.message.text.split()
    if len(params) != 4:
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
        await handle_invalid_input(update, example)
        return None

    if not await validate_time_input(
        date_str=params[2],
        time_str=params[3],
        bot=context.bot,
        chat_id=update.message.chat_id,
    ):
        return None

    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://pass.rw.by/ru/route/?from={params[0]}&to={params[1]}&date={params[2]}"
            response = await make_get_request(url=url, session=session)
            if response.status != 200:
                raise Exception(f"HTTP error {response.status}")

            soup = BeautifulSoup(await response.text(), "html.parser")
            if not await validate_rzd_response(
                params, soup, context.bot, update.message.chat_id
            ):
                return None

            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"🔍 <b>Начинаю поиск билетов</b>\n\n"
                f"🚂 <b>Маршрут:</b> {params[0]} → {params[1]}\n"
                f"📅 <b>Дата:</b> {params[2]}\n"
                f"⏰ <b>Время:</b> {params[3]}\n\n"
                "Я сообщу вам сразу, как только билеты появятся в продаже.\n\n"
                "❌ Для отмены поиска нажмите <b>Отмена</b>\n"
                "➕ Для добавления нового поиска нажмите <b>Ещё один билет</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardMarkup(
                    [["Отмена", "Ещё один билет"]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.bind(url=url, error=str(e), chat_id=update.message.chat_id).error(
                f"Ticket checking failed after retries: {settings.retry_attempts}"
            )
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Не удалось проверить билеты {params[0]} → {params[1]} "
                f"на {params[2]} {params[3]}. Сервер не отвечает.\n\n"
                f"Попробуйте снова",
            )
            return None
        except Exception as e:
            logger.bind(url=url, error=str(e), chat_id=update.message.chat_id).error(
                "Ticket checking error"
            )
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"❌ Ошибка при проверке билетов {params[0]} → {params[1]} "
                f"на {params[2]} {params[3]}"
                f"Попробуйте снова",
            )
            return None

    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    ticket_repo.add_request(
        departure=params[0],
        arrival=params[1],
        date=params[2],
        time=params[3],
        chat_id=update.message.chat_id,
        user_id=update.effective_user.id,
        user_name=update.effective_user.username,  # type: ignore
    )
    return None


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel active search tasks."""
    if (
        not update
        or not update.message
        or not update.message.text
        or update.message.text.strip().lower() != "отмена"
    ):
        return

    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    result = ticket_repo.set_request_inactive_by_chat_id(chat_id=update.message.chat_id)
    example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
    await update.message.reply_text(
        f"❌ <b>Отменено {result} поиск(а)</b>\n\n"
        "Чтобы начать новый поиск, введите:\n"
        "<code>Откуда Куда Дата Время</code>\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>{example}</code>\n\n"
        "Или нажмите /start для справки",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    user = update.effective_user
    logger.bind(
        user_id=user.id,  # type: ignore
        username=user.username,  # type: ignore
        chat_id=update.message.chat_id,
    ).debug(
        f"User {user.first_name} {user.last_name} cancelled {result} tickets"  # type: ignore
    )


async def add_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a request to add another ticket search."""
    if (
        not update
        or not update.effective_user
        or not update.message
        or not update.message.text
        or update.message.text.strip().lower() != "ещё один билет"
    ):
        return

    example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
    await update.message.reply_text(
        "📝 <b>Введите данные в формате:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "📅 <b>Дата:</b> ГГГГ-ММ-ДД\n"
        "⏰ <b>Время:</b> ЧЧ:ММ (24-часовой формат)\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>{example}</code>\n\n",
        parse_mode=ParseMode.HTML,
    )
    user = update.effective_user
    logger.bind(
        user_id=user.id, username=user.username, chat_id=update.message.chat_id
    ).debug(f"User {user.first_name} {user.last_name} wants to add another ticket")
