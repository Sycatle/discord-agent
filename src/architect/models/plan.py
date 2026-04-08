from pydantic import BaseModel, ConfigDict
from .actions import Action


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    actions: list[Action]
