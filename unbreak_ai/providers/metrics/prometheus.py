from typing import Literal

from unbreak_ai.config.schema import ProviderSettings, Secret


class PrometheusMetricsSettings(ProviderSettings):
    type: Literal["prometheus"]
    url: str
    auth: Secret | None = None
