import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _lint_imports(workdir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--config",
            "pyproject.toml",
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(workdir), "PATH": ""},
    )


def _copy_project(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "unbreak_ai", tmp_path / "unbreak_ai")
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


@pytest.mark.req("NFR-12")
def test_clean_tree_passes(tmp_path: Path) -> None:
    result = _lint_imports(_copy_project(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.req("NFR-12")
@pytest.mark.parametrize("target", ["agent", "tools", "incidents", "intake", "notifiers"])
def test_providers_importing_upstream_fails(tmp_path: Path, target: str) -> None:
    project = _copy_project(tmp_path)
    (project / "unbreak_ai" / "providers" / "bad.py").write_text(f"import unbreak_ai.{target}\n")
    result = _lint_imports(project)
    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout


@pytest.mark.req("NFR-12")
@pytest.mark.parametrize("target", ["config", "providers", "agent"])
def test_models_importing_anything_else_fails(tmp_path: Path, target: str) -> None:
    project = _copy_project(tmp_path)
    (project / "unbreak_ai" / "models" / "bad.py").write_text(f"import unbreak_ai.{target}\n")
    result = _lint_imports(project)
    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout


@pytest.mark.req("NFR-12")
@pytest.mark.parametrize(
    "target", ["providers", "notifiers", "agent", "tools", "incidents", "intake", "startup"]
)
def test_config_importing_feature_modules_fails(tmp_path: Path, target: str) -> None:
    project = _copy_project(tmp_path)
    (project / "unbreak_ai" / "config" / "bad.py").write_text(f"import unbreak_ai.{target}\n")
    result = _lint_imports(project)
    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout


@pytest.mark.req("NFR-12")
@pytest.mark.parametrize("package", ["agent", "tools", "providers", "notifiers", "models"])
def test_nothing_may_import_startup(tmp_path: Path, package: str) -> None:
    project = _copy_project(tmp_path)
    (project / "unbreak_ai" / package / "bad.py").write_text("import unbreak_ai.startup\n")
    result = _lint_imports(project)
    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout
