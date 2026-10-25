import importlib

import pytest

import unbreak_ai

PACKAGES = [
    "intake",
    "incidents",
    "agent",
    "agent.prompts",
    "tools",
    "providers",
    "providers.middleware",
    "providers.logs",
    "providers.metrics",
    "providers.traces",
    "providers.changes",
    "notifiers",
    "config",
    "observability",
    "models",
]


def test_version() -> None:
    assert unbreak_ai.__version__ == "0.1.0"


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    importlib.import_module(f"unbreak_ai.{name}")
