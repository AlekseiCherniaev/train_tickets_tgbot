import asyncio
from typing import Any

import aiohttp
import structlog
from bs4 import BeautifulSoup
from telegram import Update, ForceReply, Bot
from telegram.ext import ContextTypes

logger = structlog.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        logger.bind(update=update).error("Update message or user is None")
        return
    user = update.effective_user
    await update.message.reply_html(
        f"Привет {user.mention_html()}! Введите через пробел Откуда, Куда, Дату в формате ГГГГ-ММ-ДД и Время отправления\nНапример: Толочин Минск-Пассажирский 2025-08-07 15:29",
        reply_markup=ForceReply(selective=True),
    )
    logger.bind(user=user).info(f"User {user.id} started the conversation")


async def enter_ticket_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.message is None
        or update.effective_user is None
        or update.message.text is None
    ):
        logger.bind(update=update).error("Update message or user is None")
        return

    params = update.message.text.split()
    if len(params) != 4:
        await update.message.reply_text(
            f"Неверно введены Откуда, Куда, Дата в формате ГГГГ.ММ.ДД и Время через пробел: {update.message.text}"
            "\nНапример: Толочин Минск-Пассажирский 2025-08-07 15:29"
        )
        logger.bind(params=params).debug("Wrong ticket params")
        return

    await update.message.reply_text(
        f"🔍 Начинаю проверку билетов {params[0]} → {params[1]} на {params[2]} {params[3]}\n"
        "Я сообщу, как только билет появится в продаже."
    )

    asyncio.create_task(
        start_ticket_checking(context.bot, params, update.message.chat_id)
    )


async def start_ticket_checking(bot: Bot, params: list[str], chat_id: int) -> None:
    async with aiohttp.ClientSession() as session:
        found = await check_tickets(session, params, bot, chat_id)
        if found:
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Билет появился в продаже! {params[0]} → {params[1]} {params[2]} {params[3]}",
            )


async def check_tickets(
    session: aiohttp.ClientSession, params: list[str], bot: Bot, chat_id: int
) -> bool:
    url = (
        f"https://pass.rw.by/ru/route/?from={params[0]}&to={params[1]}&date={params[2]}"
    )
    while True:
        try:
            response = await session.get(url)
            logger.info(f"Start checking tickets for {params}, chat_id: {chat_id}")
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), "html.parser")

                target_train = await validate_ticket_params(
                    params=params, soup=soup, bot=bot, chat_id=chat_id
                )
                if not target_train:
                    return False

                ticket_available = (
                    target_train.parent.parent.parent.parent.parent.get(
                        "data-ticket_selling_allowed"
                    )
                    == "true"
                )
                if ticket_available:
                    return True
            logger.debug(f"Tickets not found for {params}, chat_id: {chat_id}")
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error checking tickets: {e}")
            await asyncio.sleep(10)


async def validate_ticket_params(
    params: list[str], soup: BeautifulSoup, bot: Bot, chat_id: int
) -> Any | None:
    error_elements = {
        "error_content": soup.find("div", class_="error_content"),
        "error_title": soup.find("div", class_="error_title"),
    }
    if any(error_elements.values()):
        error_parts = [str(el.text) for el in error_elements.values() if el]
        error_message = " | ".join(error_parts)
        await bot.send_message(
            chat_id=chat_id,
            text="Неверно введены Откуда, Куда и Дата в формате ГГГГ.ММ.ДД через пробел"
            f"\n{error_message}",
        )
        logger.bind(params=params).debug(f"Found error in RZD request: {error_message}")
        return None

    target_train = soup.find(
        "div", class_="sch-table__time train-from-time", string=params[3]
    )
    if target_train is None:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Неверно введено Время отправления: {params[3]}, поезд не найден",
        )
        logger.bind(params=params).debug(f"Found error in departure time: {params[3]}")
        return None
    return target_train
