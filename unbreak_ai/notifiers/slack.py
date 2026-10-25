from typing import Literal

from unbreak_ai.config.schema import NotifierSettings, Secret


class SlackNotifierSettings(NotifierSettings):
    type: Literal["slack"]
    channel: str
    bot_token: Secret
