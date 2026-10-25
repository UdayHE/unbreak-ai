"""Load, interpolate and validate the YAML config.

``${VAR}`` is read from the environment. Secret fields are valid only when their value was filled
from a ``${VAR}`` with no default (NFR-09), so inline and defaulted secrets are rejected.
Error text is built from each error's location and message only, never the input value.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr, ValidationError

from unbreak_ai.config.errors import UnbreakAIConfigError
from unbreak_ai.config.registry import Registries, TypeRegistry
from unbreak_ai.config.schema import NotifierSettings, ProviderSettings, UnbreakAIConfig

__all__ = ["AppConfig", "ResolvedProviders", "UnbreakAIConfigError", "load_config"]

CONFIG_ENV = "UNBREAK_AI_CONFIG"
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


@dataclass(frozen=True)
class ResolvedProviders:
    logs: list[ProviderSettings]
    metrics: list[ProviderSettings]
    traces: list[ProviderSettings]
    changes: list[ProviderSettings]


@dataclass(frozen=True)
class AppConfig:
    """The validated config plus every provider and notifier entry parsed by its registry."""

    config: UnbreakAIConfig
    providers: ResolvedProviders
    notifiers: list[NotifierSettings]


def load_config(
    path: str | Path | None, env: Mapping[str, str] | None, registries: Registries
) -> AppConfig:
    env = os.environ if env is None else env
    if path is None:
        if not env.get(CONFIG_ENV):
            raise UnbreakAIConfigError([f"no config path given and {CONFIG_ENV} is not set"])
        path = env[CONFIG_ENV]
    try:
        raw = yaml.safe_load(Path(path).read_text())
    except OSError as exc:
        raise UnbreakAIConfigError([f"cannot read {path}: {exc.strerror}"]) from None
    except yaml.YAMLError:
        raise UnbreakAIConfigError([f"{path} is not valid YAML"]) from None
    if not isinstance(raw, dict):
        raise UnbreakAIConfigError([f"{path} must contain a YAML mapping at the top level"])

    problems: list[str] = []
    env_paths: set[str] = set()
    data = _interpolate(raw, "", env, env_paths, problems)
    if problems:
        raise UnbreakAIConfigError(problems)

    # Report schema problems and entry problems together, each with its full key path.
    problems = []
    config: UnbreakAIConfig | None = None
    try:
        config = UnbreakAIConfig.model_validate(data)
    except ValidationError as exc:
        problems.extend(f"{_dotted(e['loc'])}: {e['msg']}" for e in exc.errors(include_input=False))

    logs = _parse_entries(
        registries.logs, _entries(data, "providers", "logs"), "providers.logs", problems
    )
    metrics = _parse_entries(
        registries.metrics, _entries(data, "providers", "metrics"), "providers.metrics", problems
    )
    traces = _parse_entries(
        registries.traces, _entries(data, "providers", "traces"), "providers.traces", problems
    )
    changes = _parse_entries(
        registries.changes, _entries(data, "providers", "changes"), "providers.changes", problems
    )
    notifiers = _parse_entries(
        registries.notifiers, _entries(data, "notifiers"), "notifiers", problems
    )

    # NFR-09: secrets are found by type (SecretStr), wherever they sit in a settings model.
    for secret_path in (
        (_secret_paths(config, "") if config else [])
        + _secret_paths(logs, "providers.logs")
        + _secret_paths(metrics, "providers.metrics")
        + _secret_paths(traces, "providers.traces")
        + _secret_paths(changes, "providers.changes")
        + _secret_paths(notifiers, "notifiers")
    ):
        if secret_path not in env_paths:
            problems.append(
                f"{secret_path}: secret must be set as ${{VAR}} from the environment, "
                "without a default"
            )
    if problems or config is None:
        raise UnbreakAIConfigError(problems)
    return AppConfig(config, ResolvedProviders(logs, metrics, traces, changes), notifiers)


def _entries(data: dict[str, Any], *keys: str) -> list[Any]:
    node: Any = data
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, list) else []


def _parse_entries[S: BaseModel](
    registry: TypeRegistry[S, Any], entries: list[Any], path: str, problems: list[str]
) -> list[S]:
    parsed: list[S] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue  # reported by the schema as a malformed list item
        try:
            parsed.append(registry.parse(entry, f"{path}.{index}"))
        except UnbreakAIConfigError as exc:
            problems.extend(exc.problems)
    return parsed


def _dotted(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc) or "<root>"


def _join(prefix: str, key: object) -> str:
    return f"{prefix}.{key}" if prefix else str(key)


def _interpolate(
    value: Any, path: str, env: Mapping[str, str], env_paths: set[str], problems: list[str]
) -> Any:
    if isinstance(value, dict):
        return {
            k: _interpolate(v, _join(path, k), env, env_paths, problems) for k, v in value.items()
        }
    if isinstance(value, list):
        return [
            _interpolate(v, _join(path, i), env, env_paths, problems) for i, v in enumerate(value)
        ]
    if not isinstance(value, str) or not _REF.search(value):
        return value

    used_default = False

    def substitute(match: re.Match[str]) -> str:
        nonlocal used_default
        name, default = match.group(1), match.group(2)
        if default is not None:
            used_default = True
            return env.get(name, default)
        if name not in env:
            problems.append(f"{path}: environment variable {name} is not set")
            return ""
        return env[name]

    result = _REF.sub(substitute, value)
    if not used_default:
        env_paths.add(path)
    return result


def _secret_paths(node: object, path: str) -> list[str]:
    if isinstance(node, SecretStr):
        return [path]
    if isinstance(node, BaseModel):
        return [
            p
            for name in type(node).model_fields
            for p in _secret_paths(getattr(node, name), _join(path, name))
        ]
    if isinstance(node, list):
        return [p for i, item in enumerate(node) for p in _secret_paths(item, _join(path, i))]
    if isinstance(node, dict):
        return [p for key, item in node.items() for p in _secret_paths(item, _join(path, key))]
    return []
