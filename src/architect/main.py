import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from .bot.bot import ArchitectBot
from .config import settings
from .logging_setup import setup_jsonl_handler

setup_jsonl_handler(settings.data_dir)


async def _run() -> None:
    async with ArchitectBot() as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
