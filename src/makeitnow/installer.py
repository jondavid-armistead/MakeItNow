"""Cross-platform installer/bootstrap helpers for MakeItNow."""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

from makeitnow.docker_runtime import find_compose_command


@dataclass(frozen=True)
class InstallAction:
    label: str
    command: tuple[str, ...]
    packages: tuple[str, ...] = ()
    requires_elevation: bool = False


@dataclass(frozen=True)
class RequirementStatus:
    key: str
    label: str
    installed: bool
    detail: str
    actions: tuple[InstallAction, ...] = ()
    managed_by: str | None = None


@dataclass(frozen=True)
class InstallPlan:
    platform_label: str
    requirements: tuple[RequirementStatus, ...]
    actions: tuple[InstallAction, ...]
    launcher_command: str
    notes: tuple[str, ...] = ()


def build_install_plan(repo_root: Path) -> InstallPlan:
    """Build an installation plan for the current machine."""
    platform_key = _platform_key()
    platform_label = _platform_label(platform_key)
    package_manager = _package_manager(platform_key)

    docker_installed = shutil.which("docker") is not None
    compose_installed = find_compose_command() is not None
    git_installed = shutil.which("git") is not None

    docker_actions = tuple(_docker_install_actions(platform_key, package_manager))
    compose_actions = tuple(
        _compose_install_actions(platform_key, package_manager, docker_installed)
    )
    git_actions = tuple(_git_install_actions(platform_key, package_manager))

    requirements = (
        RequirementStatus(
            key="docker",
            label="Docker",
            installed=docker_installed,
            detail=(
                "Already installed."
                if docker_installed
                else _missing_detail("Docker", package_manager)
            ),
            actions=docker_actions,
        ),
        RequirementStatus(
            key="docker-compose",
            label="Docker Compose support",
            installed=compose_installed,
            detail=_compose_detail(platform_key, package_manager, docker_installed, compose_installed),
            actions=compose_actions,
            managed_by="Docker" if (not docker_installed and package_manager is not None) else None,
        ),
        RequirementStatus(
            key="git",
            label="Git",
            installed=git_installed,
            detail=("Already installed." if git_installed else _missing_detail("Git", package_manager)),
            actions=git_actions,
        ),
    )

    notes: list[str] = []
    if platform_key == "linux":
        notes.append(
            "Linux users may still need to add themselves to the docker group and sign in again "
            "before Docker commands work without sudo."
        )

    return InstallPlan(
        platform_label=platform_label,
        requirements=requirements,
        actions=_dedupe_actions(
            action for requirement in requirements for action in requirement.actions
        ),
        launcher_command="python run_makeitnow.py https://github.com/org/my-app",
        notes=tuple(notes),
    )


def format_install_plan(plan: InstallPlan) -> str:
    """Render the install plan for the user."""
    lines = [
        f"[install] Platform: {plan.platform_label}",
        "[install] Prerequisite check:",
    ]
    for requirement in plan.requirements:
        status = "OK" if requirement.installed else "MISSING"
        lines.append(f"  - {requirement.label}: {status} - {requirement.detail}")

    if plan.actions:
        lines.append("")
        lines.append("[install] Proposed install actions:")
        for action in plan.actions:
            lines.append(f"  - {action.label}: {' '.join(action.command)}")

    if plan.notes:
        lines.append("")
        lines.append("[install] Notes:")
        for note in plan.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def format_completion_summary(
    plan: InstallPlan,
    *,
    completed_requirements: tuple[str, ...] = (),
    completed_actions: tuple[InstallAction, ...] = (),
) -> str:
    """Render the end-of-install summary and quick-start guide."""
    lines = [
        "",
        "[install] MakeItNow is ready.",
        "[install] Final dependency status:",
    ]
    for requirement in plan.requirements:
        status = "ready" if requirement.installed else "missing"
        lines.append(f"  - {requirement.label}: {status}")

    if completed_requirements or completed_actions:
        lines.append("")
        lines.append("[install] Completed during this run:")
        for requirement in completed_requirements:
            lines.append(f"  - Dependency installed: {requirement}")
        for action in completed_actions:
            packages = f" ({', '.join(action.packages)})" if action.packages else ""
            lines.append(f"  - {action.label}{packages}")

    lines.extend(
        [
            "",
            "[install] Quick start:",
            "  1. Run the local launcher without activating a virtual environment:",
            f"     {plan.launcher_command}",
            "  2. Example:",
            "     python run_makeitnow.py https://github.com/org/my-app",
        ]
    )

    if plan.notes:
        lines.append("")
        lines.append("[install] Notes:")
        for note in plan.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def run_install(repo_root: Path, *, input_func=input, print_func=print) -> int:
    """Execute the installation flow for a cloned repo."""
    plan = build_install_plan(repo_root)
    print_func(format_install_plan(plan))

    missing = [requirement for requirement in plan.requirements if not requirement.installed]
    if missing and not plan.actions:
        print_func(
            "\n[install] Automatic prerequisite installation is not configured for this platform.\n"
            "[install] Install the missing tools manually, then rerun install.py."
        )
        return 1

    completed_requirements: list[str] = []
    completed_actions: list[InstallAction] = []

    if missing:
        for requirement in missing:
            if not requirement.actions:
                if requirement.managed_by:
                    print_func(
                        f"\n[install] {requirement.label} will be handled when {requirement.managed_by} "
                        "is installed."
                    )
                    continue
                print_func(
                    f"\n[install] {requirement.label} is missing, but automatic installation is not "
                    "configured for this platform."
                )
                continue

            print_func(f"\n[install] {requirement.label} is missing.")
            for action in requirement.actions:
                if action.packages:
                    print_func(
                        f"[install] Packages/applications: {', '.join(action.packages)}"
                    )
                if action.requires_elevation:
                    print_func(
                        "[install] This step may trigger your normal sudo/administrator prompt."
                    )
                print_func(f"[install] Command: {' '.join(action.command)}")

            answer = input_func(
                f"[install] Install {requirement.label} now? [Y/n]: "
            ).strip().lower()
            if answer in {"n", "no"}:
                print_func(f"[install] Skipping {requirement.label}.")
                continue

            for action in requirement.actions:
                print_func(f"[install] Running: {' '.join(action.command)}")
                result = subprocess.run(list(action.command))
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Install step failed while running: {' '.join(action.command)}"
                    )
                completed_actions.append(action)
            completed_requirements.append(requirement.label)

    _install_package(repo_root, print_func=print_func)

    final_plan = build_install_plan(repo_root)
    print_func(
        format_completion_summary(
            final_plan,
            completed_requirements=tuple(completed_requirements),
            completed_actions=tuple(completed_actions),
        )
    )
    return 0


def main() -> None:
    """Entry point for the repo-local installer."""
    repo_root = Path(__file__).resolve().parents[2]
    raise SystemExit(run_install(repo_root))


def _install_package(repo_root: Path, *, print_func=print) -> None:
    venv_dir = repo_root / ".makeitnow-venv"
    if not venv_dir.exists():
        print_func("[install] Creating local virtual environment ...")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    else:
        print_func("[install] Reusing local virtual environment ...")

    python_executable = _venv_python(venv_dir)
    install_commands = (
        ("[install] Upgrading pip ...", [str(python_executable), "-m", "pip", "install", "--upgrade", "pip"]),
        ("[install] Installing MakeItNow ...", [str(python_executable), "-m", "pip", "install", str(repo_root)]),
    )
    for message, command in install_commands:
        print_func(message)
        result = subprocess.run(command)
        if result.returncode != 0:
            raise RuntimeError(f"Install step failed while running: {' '.join(command)}")


def _venv_python(venv_dir: Path) -> Path:
    if _platform_key() == "windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "unknown"


def _platform_label(platform_key: str) -> str:
    return {
        "windows": "Windows",
        "macos": "macOS",
        "linux": "Linux",
    }.get(platform_key, "Unknown platform")


def _package_manager(platform_key: str) -> str | None:
    if platform_key == "windows":
        return "winget" if shutil.which("winget") else None
    if platform_key == "macos":
        return "brew" if shutil.which("brew") else None
    if platform_key != "linux":
        return None

    for candidate in ("apt-get", "dnf", "yum", "pacman", "zypper"):
        if shutil.which(candidate):
            return candidate
    return None


def _docker_install_actions(platform_key: str, package_manager: str | None) -> list[InstallAction]:
    if package_manager == "winget":
        return [
            InstallAction(
                label="Install Docker Desktop",
                command=("winget", "install", "-e", "--id", "Docker.DockerDesktop"),
                packages=("Docker Desktop",),
            )
        ]
    if package_manager == "brew":
        return [
            InstallAction(
                label="Install Docker Desktop",
                command=("brew", "install", "--cask", "docker"),
                packages=("docker",),
            )
        ]
    if platform_key == "linux" and package_manager is not None:
        packages = {
            "apt-get": ("docker.io", "docker-compose-v2"),
            "dnf": ("docker", "docker-compose-plugin"),
            "yum": ("docker", "docker-compose-plugin"),
            "pacman": ("docker", "docker-compose"),
            "zypper": ("docker", "docker-compose"),
        }[package_manager]
        actions = []
        if package_manager in {"apt-get", "dnf", "yum", "zypper"}:
            actions.append(
                InstallAction(
                    label=f"Refresh {package_manager} package metadata",
                    command=("sudo", package_manager, "update")
                    if package_manager == "apt-get"
                    else ("sudo", package_manager, "makecache"),
                    packages=(),
                    requires_elevation=True,
                )
            )
        actions.append(
            InstallAction(
                label="Install Docker packages",
                command=_linux_install_command(package_manager, packages),
                packages=packages,
                requires_elevation=True,
            )
        )
        return actions
    return []


def _compose_install_actions(
    platform_key: str,
    package_manager: str | None,
    docker_installed: bool,
) -> list[InstallAction]:
    if not docker_installed:
        return []

    if package_manager == "winget":
        return [
            InstallAction(
                label="Repair Docker Desktop (includes Compose)",
                command=("winget", "install", "-e", "--id", "Docker.DockerDesktop"),
                packages=("Docker Desktop",),
            )
        ]
    if package_manager == "brew":
        return [
            InstallAction(
                label="Install docker-compose",
                command=("brew", "install", "docker-compose"),
                packages=("docker-compose",),
            )
        ]
    if platform_key == "linux" and package_manager is not None:
        package = {
            "apt-get": ("docker-compose-v2",),
            "dnf": ("docker-compose-plugin",),
            "yum": ("docker-compose-plugin",),
            "pacman": ("docker-compose",),
            "zypper": ("docker-compose",),
        }[package_manager]
        return [
            InstallAction(
                label="Install Docker Compose support",
                command=_linux_install_command(package_manager, package),
                packages=package,
                requires_elevation=True,
            )
        ]
    return []


def _git_install_actions(platform_key: str, package_manager: str | None) -> list[InstallAction]:
    if package_manager == "winget":
        return [
            InstallAction(
                label="Install Git",
                command=("winget", "install", "-e", "--id", "Git.Git"),
                packages=("Git",),
            )
        ]
    if package_manager == "brew":
        return [
            InstallAction(
                label="Install Git",
                command=("brew", "install", "git"),
                packages=("git",),
            )
        ]
    if platform_key == "linux" and package_manager is not None:
        return [
            InstallAction(
                label="Install Git",
                command=_linux_install_command(package_manager, ("git",)),
                packages=("git",),
                requires_elevation=True,
            )
        ]
    return []


def _linux_install_command(package_manager: str, packages: tuple[str, ...]) -> tuple[str, ...]:
    install_flags = {
        "apt-get": ("sudo", "apt-get", "install", "-y"),
        "dnf": ("sudo", "dnf", "install", "-y"),
        "yum": ("sudo", "yum", "install", "-y"),
        "pacman": ("sudo", "pacman", "-S", "--noconfirm"),
        "zypper": ("sudo", "zypper", "install", "-y"),
    }[package_manager]
    return (*install_flags, *packages)


def _compose_detail(
    platform_key: str,
    package_manager: str | None,
    docker_installed: bool,
    compose_installed: bool,
) -> str:
    if compose_installed:
        return "Already installed."
    if not docker_installed and package_manager is not None:
        return "Will be included when Docker is installed."
    return _missing_detail("Docker Compose support", package_manager)


def _missing_detail(tool_name: str, package_manager: str | None) -> str:
    if package_manager is None:
        return f"{tool_name} is missing and must be installed manually on this platform."
    return f"{tool_name} is missing and can be installed automatically with {package_manager}."


def _dedupe_actions(actions: object) -> tuple[InstallAction, ...]:
    seen: set[tuple[str, ...]] = set()
    unique: list[InstallAction] = []
    for action in actions:
        if action.command in seen:
            continue
        seen.add(action.command)
        unique.append(action)
    return tuple(unique)
