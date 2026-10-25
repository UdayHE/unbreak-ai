"""Generic type registry: maps a ``type`` string to its settings model and factory.

Registries are built from explicit mappings in ``providers/registry.py`` and
``notifiers/registry.py``; they are the single source of truth for known types. This module
imports nothing from ``providers`` or ``notifiers``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from unbreak_ai.config.errors import UnbreakAIConfigError


@dataclass(frozen=True)
class TypeEntry[S: BaseModel, P]:
    settings: type[S]
    # None while the adapter is not implemented yet: the type is known, but cannot be built.
    factory: Callable[[S], P] | None = None


class TypeRegistry[S: BaseModel, P]:
    def __init__(
        self,
        family: str,
        entries: Mapping[str, TypeEntry[Any, P]],
        protocol: type | None = None,
    ) -> None:
        self.family = family
        self._entries = dict(entries)
        self._protocol = protocol

    @property
    def types(self) -> list[str]:
        return sorted(self._entries)

    def parse(self, entry: Mapping[str, Any], path: str) -> S:
        """Validate one raw config entry; errors carry the full key path and never the input."""
        type_name = entry.get("type")
        if not isinstance(type_name, str) or type_name not in self._entries:
            shown = f" {type_name!r}" if isinstance(type_name, str) else ""
            allowed = ", ".join(self.types) or "none"
            raise UnbreakAIConfigError(
                [f"{path}.type: unknown {self.family} type{shown}; allowed: {allowed}"]
            )
        try:
            settings: S = self._entries[type_name].settings.model_validate(entry)
        except ValidationError as exc:
            raise UnbreakAIConfigError(
                [
                    f"{path}.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors(include_input=False)
                ]
            ) from None
        return settings

    def build(self, settings: S) -> P:
        type_name: str = settings.type  # type: ignore[attr-defined]
        factory = self._entries[type_name].factory
        if factory is None:
            raise UnbreakAIConfigError(
                [f"{self.family} type '{type_name}' is known but not implemented yet"]
            )
        built = factory(settings)
        # runtime_checkable Protocols only verify that the attribute and method names exist,
        # not their signatures or return types; the contract tests (T-07 onward) check behavior.
        if self._protocol is not None and not isinstance(built, self._protocol):
            raise UnbreakAIConfigError(
                [
                    f"{self.family} type '{type_name}' built an object that is not a "
                    f"{self._protocol.__name__}"
                ]
            )
        return built


@dataclass(frozen=True)
class Registries:
    logs: TypeRegistry[Any, Any]
    metrics: TypeRegistry[Any, Any]
    traces: TypeRegistry[Any, Any]
    changes: TypeRegistry[Any, Any]
    notifiers: TypeRegistry[Any, Any]
