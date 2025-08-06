import asyncio
import datetime

import aiohttp
import structlog
from bs4 import BeautifulSoup
from telegram import Update, Bot, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.settings import settings
from app.task_manager import task_manager

logger = structlog.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.message or not user:
        return

    message = (
        "🚂 <b>Поиск железнодорожных билетов</b>\n\n"
        "📝 <b>Введите данные в формате:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "📅 <b>Дата:</b> ГГГГ-ММ-ДД\n"
        "⏰ <b>Время:</b> ЧЧ:ММ (24-часовой формат)\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>Толочин  Минск-Пассажирский {datetime.date.today()} 07:44</code>\n\n"
        f"Можно искать до 3 билетов одновременно\n"
    )
    await update.message.reply_html(message)
    logger.bind(user_id=user.id, username=user.username).info(
        f"User {user.first_name} {user.last_name} started the conversation"
    )


async def enter_ticket_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.message.text:
        return None
    if context.user_data is None:
        context.user_data = {}
    params = update.message.text.split()
    if len(params) != 4:
        example_text = f"Толочин Минск-Пассажирский {datetime.date.today()} 07:44"
        error_message = (
            "❌ <b>Ошибка ввода данных</b>\n\n"
            "Вы ввели неверное количество параметров:\n"
            f"<code>{update.message.text}</code>\n\n"
            "📝 <b>Требуемый формат:</b>\n"
            "<code>Откуда  Куда  Дата  Время</code>\n\n"
            "🔹 <b>Пример правильного ввода:</b>\n"
            f"<code>{example_text}</code>\n\n"
            "📅 Дата в формате: <b>ГГГГ-ММ-ДД</b>\n"
            "⏰ Время в формате: <b>ЧЧ:ММ</b>"
        )
        await update.message.reply_html(
            error_message,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(params=params).debug("Wrong ticket params")
        return None

    task = asyncio.create_task(
        start_ticket_checking(context.bot, params, update.message.chat_id)
    )
    task_manager.add_task(chat_id=update.message.chat_id, task=task)

    if "search_task" not in context.user_data:
        context.user_data["search_task"] = task
    else:
        for i in range(1, settings.max_concurrent_searches + 1):
            task_key = f"search_task{i}"
            if task_key not in context.user_data or context.user_data[task_key].done():
                context.user_data[task_key] = task
                return None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await update.message.reply_text(
            "❌ <b>Достигнут лимит поисков</b>\n\n"
            f"Можно запустить не более {settings.max_concurrent_searches} одновременных поисков.\n"
            "Больше запустить не получится.\n\n",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
    return None


async def start_ticket_checking(bot: Bot, params: list[str], chat_id: int) -> None:
    async with aiohttp.ClientSession() as session:
        url = f"https://pass.rw.by/ru/route/?from={params[0]}&to={params[1]}&date={params[2]}"
        try:
            response = await session.get(url)
            if response.status == 200:
                logger.bind(url=url).info(
                    f"Validate tickets params for {params}, chat_id: {chat_id}"
                )
                soup = BeautifulSoup(await response.text(), "html.parser")
                if not await validate_ticket_params(
                    params=params, soup=soup, bot=bot, chat_id=chat_id
                ):
                    return None

                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🔍 <b>Начинаю поиск билетов</b>\n\n"
                    f"🚂 <b>Маршрут:</b> {params[0]} → {params[1]}\n"
                    f"📅 <b>Дата:</b> {params[2]}\n"
                    f"⏰ <b>Время:</b> {params[3]}\n\n"
                    "Я сообщу вам сразу, как только билеты появятся в продаже.\n\n"
                    "❌ Для отмены поиска нажмите <b>Отмена</b>\n\n"
                    "Либо введите еще один билет\n\n",
                    parse_mode=ParseMode.HTML,
                    reply_markup=ReplyKeyboardMarkup(
                        [["Отмена", "Ещё один билет"]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
        except Exception as e:
            logger.error(f"Error checking tickets: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка при проверке билетов {params[0]} → {params[1]} на {params[2]} {params[3]}, возможно, сайт не доступен",
            )
            return None

        while True:
            try:
                response = await session.get(url)
                logger.bind(url=url).debug(
                    f"Start checking tickets for {params}, chat_id: {chat_id}"
                )
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), "html.parser")
                    target_block = soup.find(
                        "div",
                        class_="sch-table__time train-from-time",
                        string=params[3],
                    )
                    train_block = target_block.parent.parent.parent.parent.parent  # type: ignore
                    ticket_available = (
                        train_block.get("data-ticket_selling_allowed") == "true"  # type: ignore
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
                        logger.debug(
                            f"Tickets found for {params}, chat_id: {chat_id}, trying again..."
                        )
                    else:
                        logger.debug(
                            f"Tickets not found for {params}, chat_id: {chat_id}, trying again..."
                        )
                await asyncio.sleep(settings.retry_time)
            except Exception as e:
                logger.error(f"Error checking tickets: {e}")
                await asyncio.sleep(settings.retry_time)


async def validate_ticket_params(
    params: list[str], soup: BeautifulSoup, bot: Bot, chat_id: int
) -> bool:
    error_elements = {
        "error_content": soup.find("div", class_="error_content"),
        "error_title": soup.find("div", class_="error_title"),
    }
    if any(error_elements.values()):
        error_parts = [str(el.text) for el in error_elements.values() if el]
        error_message = " | ".join(error_parts)
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
            f"<code>Толочин Минск-Пассажирский {datetime.date.today()} 07:44</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(params=params).debug(f"Found error in RZD request: {error_message}")
        return False

    if not soup.find("div", class_="sch-table__time train-from-time", string=params[3]):
        await bot.send_message(
            chat_id=chat_id,
            text="🚫 <b>Поезд не найден</b>\n\n"
            f"Время <b>{params[3]}</b> не найдено для указанного маршрута.\n\n"
            "ℹ <b>Проверьте:</b>\n"
            "• Неправильно указаны станции\n"
            "• Доступность рейсов на выбранное время\n"
            "• Формат времени (ЧЧ:ММ, 24-часовой)\n\n"
            f"🔹 <b>Пример запроса:</b>\n"
            f"<code>Толочин Минск-Пассажирский {datetime.date.today()} 07:44</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                [["Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        logger.bind(params=params).debug(f"Found error in departure time: {params[3]}")
        return False

    return True


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    for i in range(settings.max_concurrent_searches + 1):
        task_key = f"search_task{i}" if i > 0 else "search_task"
        if task := context.user_data.get(task_key):
            if not task.done():
                task.cancel()
                try:
                    await task
                    cancelled_count += 1
                except asyncio.CancelledError:
                    cancelled_count += 1
                except Exception as e:
                    logger.error(f"Error cancelling task {task_key}: {e}")
            context.user_data.pop(task_key, None)

    await update.message.reply_text(
        f"❌ <b>Отменено {cancelled_count} поиск(а)</b>\n\n"
        "Чтобы начать новый поиск, введите:\n"
        "<code>Откуда Куда Дата Время</code>\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>Толочин Минск-Пассажирский {datetime.date.today()} 07:44</code>\n\n"
        "Или нажмите /start для справки",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


async def add_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        not update
        or not update.effective_user
        or not update.message
        or not update.message.text
        or update.message.text.strip().lower() != "ещё один билет"
    ):
        return
    await update.message.reply_text(
        f"📝 <b>Лимит одновременного поиска: {settings.max_concurrent_searches}</b>\n"
        "📝 <b>Введите данные в формате:</b>\n"
        "<code>Откуда  Куда  Дата  Время</code>\n\n"
        "📅 <b>Дата:</b> ГГГГ-ММ-ДД\n"
        "⏰ <b>Время:</b> ЧЧ:ММ (24-часовой формат)\n\n"
        "🔹 <b>Пример:</b>\n"
        f"<code>Толочин  Минск-Пассажирский  {datetime.date.today()} 07:44</code>\n\n",
        parse_mode=ParseMode.HTML,
    )
    logger.debug(f"User {update.effective_user.username} wants to add another ticket")
