from unittest.mock import AsyncMock

import pytest
from bs4 import BeautifulSoup
from telegram import Bot

from app.handlers import validate_ticket_params

URL = "https://pass.rw.by/ru/route/?from=Толочин&to=Минск-Пассажирский&date=2025-08-07"

VALID_HTML_WITH_TICKET = """
<div class="sch-table__row">
  <div class="sch-table__time train-from-time">15:29</div>
</div>
<div data-ticket_selling_allowed="true"></div>
"""

VALID_HTML_NO_TICKET = """
<div class="sch-table__row">
  <div class="sch-table__time train-from-time">15:29</div>
</div>
<div data-ticket_selling_allowed="false"></div>
"""

ERROR_HTML = """
<div class="error_title">Ошибка</div>
<div class="error_content">Неверные данные маршрута</div>
"""


@pytest.fixture
def params() -> list[str]:
    return ["Толочин", "Минск-Пассажирский", "2025-08-07", "15:29"]


@pytest.fixture
def mock_bot() -> Bot:
    return AsyncMock(spec=Bot)


@pytest.fixture
def chat_id() -> int:
    return 1234


class TestIntegration:
    async def test_validate_ticket_params_valid(
        self, params: list[str], mock_bot: Bot, chat_id: int
    ) -> None:
        soup = BeautifulSoup(VALID_HTML_WITH_TICKET, "html.parser")
        train = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert train is not None

    async def test_validate_ticket_params_invalid_time(
        self, params: list[str], mock_bot: Bot, chat_id: int
    ) -> None:
        soup = BeautifulSoup(
            VALID_HTML_WITH_TICKET.replace("15:29", "14:00"), "html.parser"
        )
        result = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert result is False
        mock_bot.send_message.assert_awaited_once()

    async def test_validate_ticket_params_with_error(
        self, params: list[str], mock_bot: Bot, chat_id: int
    ) -> None:
        soup = BeautifulSoup(ERROR_HTML, "html.parser")
        result = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert result is False
        mock_bot.send_message.assert_awaited_once()

    async def test_validate_ticket_params_success(self, mock_bot):
        params = ["Толочин", "Минск-Пассажирский", "2023-12-25", "08:00"]
        chat_id = 12345

        mock_html = """
        <div class="sch-table__time train-from-time">08:00</div>
        """
        soup = BeautifulSoup(mock_html, "html.parser")

        result = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert result is True
        mock_bot.send_message.assert_not_called()
