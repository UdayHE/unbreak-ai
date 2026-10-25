"""The known notifier types: an explicit mapping, the single source of truth for them.

Factories are added by T-32 together with the adapters.
"""

from collections.abc import Mapping
from typing import Any

from unbreak_ai.config.registry import TypeEntry
from unbreak_ai.notifiers.email import EmailNotifierSettings
from unbreak_ai.notifiers.slack import SlackNotifierSettings

NOTIFIER_TYPES: Mapping[str, TypeEntry[Any, Any]] = {
    "slack": TypeEntry(SlackNotifierSettings),
    "email": TypeEntry(EmailNotifierSettings),
}
