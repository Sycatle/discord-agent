from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    discord_token: str
    discord_guild_id: int
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_api_key: str
    llm_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
