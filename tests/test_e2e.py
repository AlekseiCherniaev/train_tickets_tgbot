from unittest.mock import MagicMock, patch

import pytest
from telegram import Update, Message, User
from telegram.ext import CallbackContext, Application, CommandHandler, MessageHandler

from app.bot import TicketBot
from app.handlers import start, enter_ticket_data, cancel, add_ticket


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = ""
    update.message.chat_id = 12345
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    return update


@pytest.fixture
def mock_context():
    context = MagicMock(spec=CallbackContext)
    context.bot = MagicMock()
    context.user_data = {}
    return context


class TestTicketBot:
    @pytest.fixture
    def ticket_bot(self):
        with (
            patch("app.bot.PostgresDatabaseConnection") as mock_db_conn,
            patch("app.bot.TicketRequestRepository") as mock_repo,
        ):
            mock_db = MagicMock()
            mock_db_conn.return_value = mock_db
            mock_repo_instance = MagicMock()
            mock_repo.return_value = mock_repo_instance
            bot = TicketBot(token="test_token")

            mock_repo.assert_called_once_with(mock_db)

            yield bot

    @patch("app.bot.ApplicationBuilder")
    def test_start_bot(self, mock_app_builder, ticket_bot):
        mock_app = MagicMock(spec=Application)
        builder_instance = MagicMock()
        mock_app_builder.return_value = builder_instance
        builder_instance.token.return_value = builder_instance
        builder_instance.post_stop.return_value = builder_instance
        builder_instance.build.return_value = mock_app
        ticket_bot.start_bot()
        builder_instance.token.assert_called_once_with("test_token")
        builder_instance.post_stop.assert_called_once_with(ticket_bot.shutdown)
        mock_app.run_polling.assert_called_once()
        ticket_bot.ticket_repo.create_table.assert_called_once()

    def test_add_handlers(self, ticket_bot):
        mock_app = MagicMock(spec=Application)
        ticket_bot.application = mock_app
        ticket_bot.add_handlers()

        assert mock_app.add_handler.call_count == 4
        handlers_added = [args[0][0] for args in mock_app.add_handler.call_args_list]

        assert sum(isinstance(h, CommandHandler) for h in handlers_added) == 1
        assert sum(isinstance(h, MessageHandler) for h in handlers_added) == 3


class TestHandlers:
    @patch("app.handlers.logger")
    async def test_start_handler(self, mock_logger, mock_update, mock_context):
        await start(mock_update, mock_context)
        mock_update.message.reply_html.assert_called_once()
        mock_logger.bind.return_value.info.assert_called_once()

    @pytest.mark.parametrize(
        "input_text,expected_calls",
        [
            ("", 0),  # No message text
            ("Only three params", 1),  # Should show error for invalid format
            (
                "Толочин Минск-Пассажирский 2023-12-01",
                1,
            ),  # Should show error for missing time
            (
                "Толочин Минск-Пассажирский 2023-12-01 07:44",
                0,
            ),  # Correct format (no immediate reply)
        ],
    )
    async def test_enter_ticket_data_handler(
        self, input_text, expected_calls, mock_update, mock_context
    ):
        mock_update.message.text = input_text
        mock_context.user_data = {}
        await enter_ticket_data(mock_update, mock_context)
        assert mock_update.message.reply_html.call_count == expected_calls
        if expected_calls > 0:
            assert (
                "Ошибка ввода данных" in mock_update.message.reply_html.call_args[0][0]
            )

    @pytest.mark.parametrize(
        "input_text,should_respond",
        [
            ("отмена", True),
            ("Отмена", True),
            ("cancel", False),  # Not in our cancel list
            ("Ещё один билет", False),  # Different command
        ],
    )
    async def test_cancel_handler(
        self, input_text, should_respond, mock_update, mock_context
    ):
        mock_update.message.text = input_text
        mock_context.user_data = {"search_task": MagicMock()}
        await cancel(mock_update, mock_context)
        if should_respond:
            mock_update.message.reply_text.assert_called_once()
            assert "Отменено" in mock_update.message.reply_text.call_args[0][0]
        else:
            mock_update.message.reply_text.assert_not_called()

    async def test_add_ticket_handler(self, mock_update, mock_context):
        mock_update.message.text = "Ещё один билет"
        await add_ticket(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        assert (
            "Лимит одновременного поиска"
            in mock_update.message.reply_text.call_args[0][0]
        )
