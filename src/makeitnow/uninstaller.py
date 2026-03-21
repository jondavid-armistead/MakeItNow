"""Repo-local uninstall helpers for MakeItNow."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from makeitnow.install_artifacts import removable_artifact_paths


@dataclass(frozen=True)
class RemovalTarget:
    label: str
    path: Path
    exists: bool


@dataclass(frozen=True)
class UninstallPlan:
    targets: tuple[RemovalTarget, ...]
    untouched_items: tuple[str, ...]


def build_uninstall_plan(repo_root: Path) -> UninstallPlan:
    """Describe which repo-local artifacts uninstall will target."""
    labels = {
        ".makeitnow-venv": "Repo-local virtual environment",
        "install.py": "Installer entry script",
        "run_makeitnow.py": "Launcher entry script",
    }
    targets = tuple(
        RemovalTarget(
            label=labels[path.name],
            path=path,
            exists=path.exists(),
        )
        for path in removable_artifact_paths(repo_root)
    )
    return UninstallPlan(
        targets=targets,
        untouched_items=("Docker", "Docker Compose", "Git", "Python", "system packages/applications"),
    )


def format_uninstall_plan(plan: UninstallPlan) -> str:
    """Render the uninstall plan for the user."""
    lines = ["[uninstall] The following MakeItNow artifacts are eligible for removal:"]
    for target in plan.targets:
        status = "present" if target.exists else "already absent"
        lines.append(f"  - {target.label}: {target.path} ({status})")

    lines.append("")
    lines.append("[uninstall] The following are intentionally left installed:")
    for item in plan.untouched_items:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def format_uninstall_summary(
    plan: UninstallPlan,
    *,
    removed_targets: tuple[RemovalTarget, ...] = (),
) -> str:
    """Render the uninstall completion summary."""
    lines = ["", "[uninstall] MakeItNow uninstall complete."]
    if removed_targets:
        lines.append("[uninstall] Removed during this run:")
        for target in removed_targets:
            lines.append(f"  - {target.label}: {target.path}")
    else:
        lines.append("[uninstall] No MakeItNow-managed artifacts were present to remove.")

    lines.append("")
    lines.append("[uninstall] Left installed:")
    for item in plan.untouched_items:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def run_uninstall(repo_root: Path, *, input_func=input, print_func=print) -> int:
    """Remove the agreed repo-local MakeItNow artifacts."""
    plan = build_uninstall_plan(repo_root)
    print_func(format_uninstall_plan(plan))

    removable_targets = [target for target in plan.targets if target.exists]
    if not removable_targets:
        print_func("[uninstall] Nothing to remove.")
        return 0

    answer = input_func("\n[uninstall] Remove these artifacts now? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print_func("[uninstall] Uninstall cancelled.")
        return 1

    removed_targets: list[RemovalTarget] = []
    for target in removable_targets:
        print_func(f"[uninstall] Removing {target.label}: {target.path}")
        if target.path.is_dir():
            shutil.rmtree(target.path)
        else:
            target.path.unlink()
        removed_targets.append(target)

    final_plan = build_uninstall_plan(repo_root)
    print_func(format_uninstall_summary(final_plan, removed_targets=tuple(removed_targets)))
    return 0


def main() -> None:
    """Entry point for the repo-local uninstaller."""
    repo_root = Path(__file__).resolve().parents[2]
    raise SystemExit(run_uninstall(repo_root))
