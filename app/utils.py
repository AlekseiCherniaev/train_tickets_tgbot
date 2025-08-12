import asyncio
import datetime
import random
from zoneinfo import ZoneInfo

import aiohttp
import structlog
from aiohttp import ClientSession, ClientResponse
from bs4 import BeautifulSoup
from telegram import ReplyKeyboardMarkup, Bot, Update
from telegram.constants import ParseMode
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.constants import headers, EXAMPLE_ROUTE, DATE_FORMAT
from app.settings import settings

logger = structlog.get_logger(__name__)


def get_minsk_date() -> datetime.date:
    return (datetime.datetime.now(ZoneInfo("Europe/Minsk"))).date()


def get_proxy_url() -> str:
    return f"http://{settings.proxy_login}:{settings.proxy_password}@{settings.proxy_host}:{settings.proxy_port}"


@retry(
    stop=stop_after_attempt(settings.retry_attempts),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def make_get_request(url: str, session: ClientSession) -> ClientResponse:
    try:
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        kwargs = {"headers": headers, "timeout": timeout}
        if settings.use_proxy:
            kwargs["proxy"] = get_proxy_url()
            logger.bind(url=url).debug("Making request with proxy...")
        else:
            logger.bind(url=url).debug("Making request without proxy...")
        return await session.get(url, **kwargs)  # type: ignore
    except Exception as e:
        logger.bind(url=url).error(f"Request failed: {e}", exception=e)
        raise e


def calculate_retry_time(base_delay: float = settings.retry_time) -> float:
    variation = base_delay * 0.25
    return random.uniform(base_delay - variation, base_delay + variation)


async def validate_time_input(
    date_str: str, time_str: str, bot: Bot, chat_id: int
) -> bool:
    """Validate if the input time is in the future."""
    logger.bind(date_str=date_str, time_str=time_str, chat_id=chat_id).debug(
        "Validating time params..."
    )
    try:
        input_time = datetime.time.fromisoformat(time_str)
        input_date = datetime.datetime.strptime(date_str, DATE_FORMAT).date()
    except ValueError:
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
        await bot.send_message(
            chat_id=chat_id,
            text="❌ <b>Неверный формат даты или времени</b>\n\n"
            f"📝 <b>Попробуйте снова:</b>\n"
            f"<code>{example}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(date_str=date_str, time_str=time_str, chat_id=chat_id).debug(
            "Wrong date or time format"
        )
        return False

    minsk_now = datetime.datetime.now(ZoneInfo("Europe/Minsk"))
    current_date = minsk_now.date()
    current_time = minsk_now.time()
    if (
        len(time_str) != 5
        or input_date < current_date
        or (input_date == current_date and input_time < current_time)
    ):
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
        await bot.send_message(
            chat_id=chat_id,
            text="❌ <b>Ошибка при поиске маршрута</b>\n\n"
            "⚡ <b>Возможные причины:</b>\n"
            "• Неправильно указано время\n"
            "• Время указано в прошлом\n"
            f"📝 <b>Попробуйте снова:</b>\n"
            f"<code>{example}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(
            input_date=input_date, input_time=input_time, chat_id=chat_id
        ).debug("Time is in the past")
        return False
    logger.bind(
        checked_date=input_date, checked_time=input_time, chat_id=chat_id
    ).debug(f"Valid time params: {date_str}, {time_str}")
    return True


async def validate_rzd_response(
    params: list[str], soup: BeautifulSoup, bot: Bot, chat_id: int
) -> bool:
    """Validate the response from the RZD website."""
    logger.bind(params=params, chat_id=chat_id).debug("Validating train params...")
    error_elements = {
        "error_content": soup.find("div", class_="error_content"),
        "error_title": soup.find("div", class_="error_title"),
    }

    if any(error_elements.values()):
        error_parts = [el.text.strip() for el in error_elements.values() if el]
        error_message = " | ".join(error_parts)
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"

        await bot.send_message(
            chat_id=chat_id,
            text="❌ <b>Ошибка при поиске маршрута</b>\n\n"
            "⚡ <b>Возможные причины:</b>\n"
            "• Неправильно указаны станции\n"
            "• Нет соединения между станциями\n"
            "• Дата указана в прошлом\n\n"
            f"🔍 <b>Подробности ошибки:</b>\n"
            f"{error_message}\n\n"
            f"📝 <b>Попробуйте снова:</b>\n"
            f"<code>{example}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(params=params, chat_id=chat_id, error_message=error_message).debug(
            "RZD request error"
        )
        return False

    # Check if train time exists
    if not soup.find("div", class_="sch-table__time train-from-time", string=params[3]):
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"

        await bot.send_message(
            chat_id=chat_id,
            text="🚫 <b>Поезд не найден</b>\n\n"
            f"Время <b>{params[3]}</b> не найдено для указанного маршрута.\n\n"
            "ℹ <b>Проверьте:</b>\n"
            "• Неправильно указаны станции\n"
            "• Доступность рейсов на выбранное время\n"
            "• Формат времени (ЧЧ:ММ, 24-часовой)\n\n"
            f"🔹 <b>Пример запроса:</b>\n"
            f"<code>{example}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(params=params, chat_id=chat_id).debug("Departure time not found")
        return False
    logger.bind(params=params, chat_id=chat_id).debug(f"Valid train params: {params}")
    return True


async def handle_invalid_input(update: Update, example: str) -> None:
    """Handle cases with invalid input format."""
    error_message = (
        "❌ <b>Ошибка ввода данных</b>\n\n"
        "Вы ввели неверное количество параметров:\n"
        f"<code>{update.message.text}</code>\n\n"  # type: ignore
        "📝 <b>Требуемый формат:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "🔹 <b>Пример правильного ввода:</b>\n"
        f"<code>{example}</code>\n\n"
        "📅 Дата в формате: <b>ГГГГ-ММ-ДД</b>\n"
        "⏰ Время в формате: <b>ЧЧ:ММ</b>"
    )
    await update.message.reply_html(  # type: ignore
        error_message,
        reply_markup=ReplyKeyboardMarkup(
            [["Отмена"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    logger.bind(params=update.message.text).debug("Wrong ticket params")  # type: ignore
