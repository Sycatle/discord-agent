from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    discord_token: str
    # Accept either DISCORD_GUILD_IDS (CSV, preferred) or the legacy
    # DISCORD_GUILD_ID (single int) so existing .env files keep working
    # after the multi-guild migration. NoDecode disables pydantic-settings'
    # built-in JSON parsing for list types — it would otherwise try to
    # json.loads("123,456") and fail before the field validator runs.
    discord_guild_ids: Annotated[list[int], NoDecode] = Field(
        validation_alias=AliasChoices("discord_guild_ids", "discord_guild_id"),
    )
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_api_key: str
    llm_model: str = ""
    llm_plan_model: str = "claude-opus-4-7"
    data_dir: Path = Path("data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("discord_guild_ids", mode="before")
    @classmethod
    def _parse_guild_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v


settings = Settings()
