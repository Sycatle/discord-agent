from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    discord_token: str
    discord_guild_id: int
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_api_key: str
    llm_model: str = ""
    llm_plan_model: str = "claude-opus-4-6"
    data_dir: Path = Path("data")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
