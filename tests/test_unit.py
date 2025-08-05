from unittest.mock import MagicMock, AsyncMock

import pytest
from telegram import User

from app.handlers import start, echo


@pytest.fixture
def mock_user() -> User:
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    mock_user.mention_html.return_value = "<a href='tg://user?id=123'>Test User</a>"
    return mock_user


class TestHandlers:
    async def test_start_handler(self, mock_user: User) -> None:
        mock_message = AsyncMock()
        mock_update = MagicMock()
        mock_update.effective_user = mock_user
        mock_update.message = mock_message

        await start(mock_update, None)  # type: ignore
        mock_message.reply_html.assert_awaited_once()

    async def test_echo_handler(self) -> None:
        mock_message = AsyncMock()
        mock_update = MagicMock()
        mock_update.message = mock_message

        await echo(mock_update, None)  # type: ignore
        mock_message.reply_text.assert_awaited_once()
