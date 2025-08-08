import asyncio
import datetime
import random
from zoneinfo import ZoneInfo

import aiohttp
import structlog
from aiohttp import ClientSession, ClientResponse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.constants import headers
from app.settings import settings

logger = structlog.getLogger(__name__)


def get_minsk_date() -> datetime.date:
    return (datetime.datetime.now(ZoneInfo("Europe/Minsk"))).date()


def get_proxy_url() -> str:
    return f"http://{settings.proxy_login}:{settings.proxy_password}@{settings.proxy_host}:{settings.proxy_port}"


@retry(
    stop=stop_after_attempt(settings.retry_attempts),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def make_get_request(url: str, session: ClientSession) -> ClientResponse:
    try:
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        kwargs = {"headers": headers, "timeout": timeout}
        if settings.use_proxy:
            kwargs["proxy"] = get_proxy_url()
            logger.debug("Using proxy...")
        else:
            logger.debug("Using direct connection...")
        return await session.get(url, **kwargs)  # type: ignore
    except Exception as e:
        logger.error(f"Request failed: {e}", exception=e)
        raise e


def calculate_retry_time(base_delay: float = settings.retry_time) -> float:
    variation = base_delay * 0.25
    return random.uniform(base_delay - variation, base_delay + variation)
