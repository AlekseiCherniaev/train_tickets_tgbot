import asyncio
import datetime
from zoneinfo import ZoneInfo

import aiohttp
import structlog
from bs4 import BeautifulSoup
from telegram import Update, Bot, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.constants import DATE_FORMAT, EXAMPLE_ROUTE
from app.settings import settings
from app.task_manager import task_manager

logger = structlog.getLogger(__name__)


def get_minsk_date() -> datetime.date:
    return (datetime.datetime.now(ZoneInfo("Europe/Minsk"))).date()


async def validate_time_input(
    date_str: str, time_str: str, bot: Bot, chat_id: int
) -> bool:
    """Validate if the input time is in the future."""
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
        logger.bind(date_str=date_str, time_str=time_str).debug(
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
        logger.bind(input_date=input_date, input_time=input_time).debug(
            "Time is in the past"
        )
        return False
    return True


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
        f"Можно искать до {settings.max_concurrent_searches} билетов одновременно\n"
    )
    await update.message.reply_html(message)
    logger.bind(user_id=user.id, username=user.username).info(
        f"User {user.first_name} {user.last_name} started bot"
    )


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
    logger.debug("Wrong ticket params", params=update.message.text.split())  # type: ignore


async def create_search_task(
    bot: Bot,
    params: list[str],
    chat_id: int,
    user_data: dict,  # type: ignore
) -> bool:
    """Create and manage search tasks with concurrency limits."""
    task = asyncio.create_task(start_ticket_checking(bot, params, chat_id))
    task_manager.add_task(chat_id=chat_id, task=task)

    for i in range(1, settings.max_concurrent_searches + 1):
        task_key = f"search_task_{i}"
        if task_key not in user_data or user_data[task_key].done():
            user_data[task_key] = task
            return True

    # Cancel a task if limit reached
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return False


async def enter_ticket_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user input for ticket search."""
    if not update.message or not update.effective_user or not update.message.text:
        return None
    if context.user_data is None:
        context.user_data = {}

    params = update.message.text.split()
    if len(params) != 4:
        example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
        await handle_invalid_input(update, example)
        return None

    task_created = await create_search_task(
        context.bot, params, update.message.chat_id, context.user_data
    )

    if not task_created:
        await update.message.reply_text(
            "❌ <b>Достигнут лимит поисков</b>\n\n"
            f"Можно запустить не более {settings.max_concurrent_searches} одновременных поисков.\n",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
    return None


async def validate_rzd_response(
    params: list[str], soup: BeautifulSoup, bot: Bot, chat_id: int
) -> bool:
    """Validate the response from the RZD website."""
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
        logger.debug("RZD request error", params=params, error=error_message)
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
        logger.debug("Departure time not found", params=params, time=params[3])
        return False

    return True


async def start_ticket_checking(bot: Bot, params: list[str], chat_id: int) -> None:
    """Main function to check ticket availability periodically."""
    url = (
        f"https://pass.rw.by/ru/route/?from={params[0]}&to={params[1]}&date={params[2]}"
    )
    async with aiohttp.ClientSession() as session:
        try:
            logger.debug("Validating ticket params", params=params, chat_id=chat_id)
            if not await validate_time_input(
                date_str=params[2], time_str=params[3], bot=bot, chat_id=chat_id
            ):
                return None

            response = await session.get(url)
            if response.status != 200:
                raise Exception(f"HTTP error {response.status}")

            soup = BeautifulSoup(await response.text(), "html.parser")
            if not await validate_rzd_response(params, soup, bot, chat_id):
                return None

            await bot.send_message(
                chat_id=chat_id,
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

            await monitor_ticket_availability(session, url, params, bot, chat_id)
            return None
        except Exception as e:
            logger.error(f"Ticket checking {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка при проверке билетов {params[0]} → {params[1]} "
                f"на {params[2]} {params[3]}, возможно, сайт не доступен",
            )
            return None


async def monitor_ticket_availability(
    session: aiohttp.ClientSession, url: str, params: list[str], bot: Bot, chat_id: int
) -> None:
    """Periodically check ticket availability."""
    while True:
        try:
            response = await session.get(url)
            if response.status != 200:
                await asyncio.sleep(settings.retry_time)
                continue

            soup = BeautifulSoup(await response.text(), "html.parser")
            target_block = soup.find(
                "div",
                class_="sch-table__time train-from-time",
                string=params[3],
            )

            if not target_block or (
                (
                    train_block := target_block.find_parent(
                        "div", class_="sch-table__row"
                    )
                )
                is None
            ):
                logger.error(
                    "Target block not found, wrong train parameters", params=params
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Ошибка при проверке билетов {params[0]} → {params[1]} "
                    f"неверно указаны станции или время",
                    reply_markup=ReplyKeyboardMarkup(
                        [["Отмена"]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                return None

            ticket_available = (
                train_block.get("data-ticket_selling_allowed", "").lower() == "true"  # type: ignore
            )

            if ticket_available:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Билет появился в продаже! {params[0]} → {params[1]} {params[2]} {params[3]}",
                    reply_markup=ReplyKeyboardMarkup(
                        [["Отмена"]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                logger.info("Tickets found", params=params, chat_id=chat_id)
            else:
                logger.debug("No available tickets", params=params, chat_id=chat_id)
            await asyncio.sleep(settings.retry_time)

        except Exception as e:
            logger.error("Monitoring error", error=str(e))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel active search tasks."""
    if (
        not update
        or not update.message
        or not update.message.text
        or update.message.text.strip().lower() != "отмена"
    ):
        return
    if not context.user_data:
        await update.message.reply_text("Нет активного поиска для отмены")
        return

    cancelled_count = 0
    for i in range(1, settings.max_concurrent_searches + 1):
        task_key = f"search_task_{i}"
        if task := context.user_data.get(task_key):
            if not task.done():
                task.cancel()
                try:
                    await task
                    cancelled_count += 1
                except asyncio.CancelledError:
                    cancelled_count += 1
                except Exception as e:
                    logger.error(
                        "Task cancellation error", task_key=task_key, error=str(e)
                    )
            context.user_data.pop(task_key, None)

    example = f"{EXAMPLE_ROUTE} {get_minsk_date().strftime(DATE_FORMAT)} 07:44"
    await update.message.reply_text(
        f"❌ <b>Отменено {cancelled_count} поиск(а)</b>\n\n"
        "Чтобы начать новый поиск, введите:\n"
        "<code>Откуда Куда Дата Время</code>\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>{example}</code>\n\n"
        "Или нажмите /start для справки",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


async def add_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle request to add another ticket search."""
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
        f"📝 <b>Лимит одновременного поиска: {settings.max_concurrent_searches}</b>\n"
        "📝 <b>Введите данные в формате:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "📅 <b>Дата:</b> ГГГГ-ММ-ДД\n"
        "⏰ <b>Время:</b> ЧЧ:ММ (24-часовой формат)\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>{example}</code>\n\n",
        parse_mode=ParseMode.HTML,
    )
    logger.debug(f"User {update.effective_user.username} wants to add another ticket")
