from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest
from bs4 import BeautifulSoup
from telegram import User, Message, Update, Bot
from telegram.ext import ContextTypes

from app.handlers import (
    start,
    validate_ticket_params,
)


@pytest.fixture
def mock_user() -> User:
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    mock_user.mention_html.return_value = "<a href='tg://user?id=123'>Test User</a>"
    return mock_user


@pytest.fixture
def mock_message() -> Message:
    mock_message = AsyncMock(spec=Message)
    mock_message.text = "Test Message"
    return AsyncMock(spec=Message)


@pytest.fixture
def mock_update(mock_user: User, mock_message: Message) -> Update:
    mock_update = MagicMock()
    mock_update.effective_user = mock_user
    mock_update.message = mock_message
    return mock_update


@pytest.fixture
def mock_logger() -> Any:
    mock_logger = MagicMock()
    mock_logger.bind.return_value = MagicMock()
    return mock_logger


@pytest.fixture
def mock_context() -> ContextTypes.DEFAULT_TYPE:
    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    return mock_context


@pytest.fixture
def valid_ticket_params_str() -> str:
    return "One two three four"


@pytest.fixture
def valid_params() -> list[str]:
    return ["Москва", "Санкт-Петербург", "2025-08-01", "15:00"]


@pytest.fixture
def chat_id() -> int:
    return 123456789


@pytest.fixture
def mock_bot() -> Bot:
    return AsyncMock(spec=Bot)


@pytest.fixture
def mock_soup() -> BeautifulSoup:
    return MagicMock(spec=BeautifulSoup)


class TestHandlers:
    async def test_start_handler(
        self, mock_user: User, mock_message: Message, mock_update: Update
    ) -> None:
        await start(mock_update, None)
        mock_message.reply_html.assert_awaited_once()

    async def test_validate_ticket_params_success(
        self,
        mock_bot: Bot,
        mock_soup: BeautifulSoup,
        valid_params: list[str],
        chat_id: int,
    ) -> None:
        mock_soup.find.side_effect = [None, None, MagicMock(text="15:00")]
        result = await validate_ticket_params(
            valid_params, mock_soup, mock_bot, chat_id
        )
        assert result is not None
        mock_bot.send_message.assert_not_awaited()

    async def test_validate_ticket_params_error_content(
        self,
        mock_bot: Bot,
        mock_soup: BeautifulSoup,
        valid_params: list[str],
        chat_id: int,
    ) -> None:
        error_div = MagicMock()
        error_div.text = "Неверная станция"
        mock_soup.find.side_effect = [error_div, None, None]
        result = await validate_ticket_params(
            valid_params, mock_soup, mock_bot, chat_id
        )

        assert result is False
        mock_bot.send_message.assert_awaited_once_with(
            chat_id=123456789,
            text="❌ <b>Ошибка при поиске маршрута</b>\n\n⚡ <b>Возможные причины:</b>\n• Неправильно указаны станции\n• Нет соединения между станциями\n• Дата указана в прошлом\n\n🔍 <b>Подробности ошибки:</b>\nНеверная станция\n\n📝 <b>Попробуйте снова:</b>\n<code>Толочин Минск-Пассажирский 2025-08-06 07:44</code>",
            parse_mode="HTML",
        )
