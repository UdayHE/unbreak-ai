"""Load, interpolate and validate the YAML config.

``${VAR}`` is read from the environment. Secret fields are valid only when their value was filled
from a ``${VAR}`` with no default (NFR-09), so inline and defaulted secrets are rejected.
Error text is built from each error's location and message only, never the input value.
"""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr, ValidationError

from unbreak_ai.config.schema import UnbreakAIConfig

CONFIG_ENV = "UNBREAK_AI_CONFIG"
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class UnbreakAIConfigError(Exception):
    """Raised when the config cannot be loaded; the message lists every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid configuration:\n" + "\n".join(f"  - {p}" for p in problems))


def load_config(
    path: str | Path | None = None, env: Mapping[str, str] | None = None
) -> UnbreakAIConfig:
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

    try:
        config = UnbreakAIConfig.model_validate(data)
    except ValidationError as exc:
        raise UnbreakAIConfigError(
            [f"{_dotted(e['loc'])}: {e['msg']}" for e in exc.errors(include_input=False)]
        ) from None

    bad = [
        f"{secret_path}: secret must be set as ${{VAR}} from the environment, without a default"
        for secret_path in _secret_paths(config, "")
        if secret_path not in env_paths
    ]
    if bad:
        raise UnbreakAIConfigError(bad)
    return config


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
    return []
