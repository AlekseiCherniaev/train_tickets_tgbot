from unittest.mock import AsyncMock, patch

import pytest
from bs4 import BeautifulSoup
from telegram import Bot

from app.handlers import start_ticket_checking, validate_ticket_params

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
        train = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert train is None
        mock_bot.send_message.assert_awaited_once()

    async def test_validate_ticket_params_with_error(
        self, params: list[str], mock_bot: Bot, chat_id: int
    ) -> None:
        soup = BeautifulSoup(ERROR_HTML, "html.parser")
        train = await validate_ticket_params(params, soup, mock_bot, chat_id)
        assert train is None
        mock_bot.send_message.assert_awaited_once()

    async def test_start_ticket_checking_success(
        self, params: list[str], chat_id: int
    ) -> None:
        bot = AsyncMock(spec=Bot)
        with patch("app.handlers.check_tickets", return_value=True):
            await start_ticket_checking(bot, params, chat_id=1234)

            bot.send_message.assert_awaited_once_with(
                chat_id=1234,
                text=f"✅ Билет появился в продаже! {params[0]} → {params[1]} {params[2]} {params[3]}",
            )
