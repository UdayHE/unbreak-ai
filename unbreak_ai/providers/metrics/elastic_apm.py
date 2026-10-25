from typing import Literal

from unbreak_ai.config.schema import ProviderSettings, Secret


class ElasticAPMMetricsSettings(ProviderSettings):
    type: Literal["elastic_apm"]
    url: str
    api_key: Secret
