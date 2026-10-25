from typing import Literal

from pydantic import Field

from unbreak_ai.config.schema import ProviderSettings, Secret


class GitHubChangesSettings(ProviderSettings):
    type: Literal["github"]
    token: Secret
    repos: list[str] = Field(min_length=1)
    config_paths: list[str] = []
