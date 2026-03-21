"""Shared paths for repo-local MakeItNow install artifacts."""

from __future__ import annotations

from pathlib import Path


LOCAL_VENV_DIRNAME = ".makeitnow-venv"
REMOVABLE_REPO_FILES = ("install.py", "run_makeitnow.py")


def local_venv_path(repo_root: Path) -> Path:
    """Return the repo-local virtual environment path."""
    return repo_root / LOCAL_VENV_DIRNAME


def removable_artifact_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return the repo-local artifacts uninstall is allowed to remove."""
    return (local_venv_path(repo_root), *(repo_root / name for name in REMOVABLE_REPO_FILES))
