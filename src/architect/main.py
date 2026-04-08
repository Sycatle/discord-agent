import asyncio

from .bot.bot import ArchitectBot
from .config import settings


async def _run() -> None:
    async with ArchitectBot() as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
