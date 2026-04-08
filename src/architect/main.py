import asyncio

from .bot.bot import ArchitectBot
from .config import settings


def main() -> None:
    bot = ArchitectBot()
    asyncio.run(bot.start(settings.discord_token))


if __name__ == "__main__":
    main()
