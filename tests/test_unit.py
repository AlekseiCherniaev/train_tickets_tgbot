from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from bs4 import BeautifulSoup
from telegram import User, Message, Update, Bot
from telegram.ext import ContextTypes

from app.handlers import (
    start,
    enter_ticket_data,
    start_ticket_checking,
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
        mock_user.mention_html.assert_called_once()

    async def test_enter_ticket_data_none_user(self, mock_logger: Any) -> None:
        mock_update = MagicMock()
        mock_update.effective_user = None

        with patch("app.handlers.logger", mock_logger):
            await enter_ticket_data(mock_update, None)
        mock_logger.bind.assert_called_once()
        mock_logger.bind.return_value.error.assert_called_once_with(
            "Update message or user is None"
        )

    async def test_enter_ticket_data_invalid_params(
        self,
        mock_user: User,
        mock_message: Message,
        mock_update: Update,
        mock_logger: Any,
    ) -> None:
        with patch("app.handlers.logger", mock_logger):
            await enter_ticket_data(mock_update, None)
        mock_message.reply_text.assert_awaited_once()
        mock_logger.bind.assert_called_once()
        mock_logger.bind.return_value.debug.assert_called_once_with(
            "Wrong ticket params"
        )

    async def test_enter_ticket_data_valid_params(
        self,
        mock_user: User,
        mock_message: Message,
        mock_update: Update,
        mock_logger: Any,
        mock_context: ContextTypes.DEFAULT_TYPE,
        valid_ticket_params_str: str,
    ) -> None:
        mock_message.text = valid_ticket_params_str
        await enter_ticket_data(mock_update, mock_context)
        mock_message.reply_text.assert_awaited_once_with(
            "🔍 Начинаю проверку билетов One → two на three four\nЯ сообщу, как только билет появится в продаже."
        )

    async def test_start_ticket_checking(
        self, valid_ticket_params_str: str, chat_id: int
    ) -> None:
        mock_bot = MagicMock(spec=Bot)
        params = valid_ticket_params_str.split()
        with patch("app.handlers.check_tickets", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            await start_ticket_checking(mock_bot, params, chat_id)
            mock_check.assert_awaited_once()
            mock_bot.send_message.assert_awaited_once_with(
                chat_id=chat_id,
                text="✅ Билет появился в продаже! One → two three four",
            )

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

        assert result is None
        mock_bot.send_message.assert_awaited_once_with(
            chat_id=123456789,
            text="Неверно введены Откуда, Куда и Дата в формате ГГГГ.ММ.ДД через пробел\nНеверная станция",
        )
