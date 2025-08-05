import structlog
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

logger = structlog.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        logger.bind(update=update).error("Update message or user is None")
        return
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}!", reply_markup=ForceReply(selective=True)
    )
    logger.bind(user=user).info(f"User {user.id} started the conversation")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        logger.bind(update=update).error("Update message or user is None")
        return
    await update.message.reply_text("Help!")
    logger.bind(user=update.effective_user).info(
        f"User {update.effective_user.id} asked for help"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        update.message is None
        or update.effective_user is None
        or update.message.text is None
    ):
        logger.bind(update=update).error("Update message or user is None")
        return
    await update.message.reply_text(update.message.text)
    logger.bind(user=update.effective_user).info(
        f"User {update.effective_user.id} sent a message"
    )
