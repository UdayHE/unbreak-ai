from typing import Literal

from unbreak_ai.config.schema import ProviderSettings, Secret


class ElasticsearchLogsSettings(ProviderSettings):
    type: Literal["elasticsearch"]
    url: str
    api_key: Secret
    regions: list[str] = []
