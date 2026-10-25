from typing import Literal

from pydantic import Field

from unbreak_ai.config.schema import NotifierSettings, Secret


class EmailNotifierSettings(NotifierSettings):
    type: Literal["email"]
    to: list[str] = Field(min_length=1)
    smtp_url: Secret
