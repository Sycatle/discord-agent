import asyncio
import logging

from architect.bot.bot import ArchitectBot
from architect.config import settings
from architect.logging_setup import setup_jsonl_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

setup_jsonl_handler(settings.data_dir)


async def _run() -> None:
    async with ArchitectBot() as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
