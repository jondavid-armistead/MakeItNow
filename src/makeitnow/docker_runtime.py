"""Docker runtime detection and diagnostics helpers."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence


def ensure_docker_access() -> None:
    """Raise a RuntimeError when Docker is unavailable or unreachable."""
    if not shutil.which("docker"):
        raise RuntimeError(
            "Docker was not found on PATH.\n"
            "Install Docker and try again: https://docs.docker.com/get-docker/"
        )

    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(classify_docker_failure("docker info", result.returncode, details))


def find_compose_command() -> list[str] | None:
    """Return the preferred compose invocation, or None if unavailable."""
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return ["docker", "compose"]

    if shutil.which("docker-compose"):
        return ["docker-compose"]

    return None


def ensure_compose_available() -> list[str]:
    """Return the compose command to use, or raise if none is available."""
    command = find_compose_command()
    if command is None:
        raise RuntimeError(
            "Docker Compose is not available.\n"
            "Install the Docker Compose plugin (or docker-compose) and try again."
        )
    return command


def run_docker_command(
    command: Sequence[str],
    *,
    action: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a Docker-related command and raise an actionable RuntimeError on failure."""
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=env,
            text=True,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        executable = command[0]
        if executable == "docker-compose":
            raise RuntimeError(
                "Docker Compose is not available.\n"
                "Install the Docker Compose plugin (or docker-compose) and try again."
            ) from None
        raise RuntimeError(
            "Docker was not found on PATH.\n"
            "Install Docker and try again: https://docs.docker.com/get-docker/"
        ) from None

    if result.returncode != 0:
        details = (result.stderr or "").strip()
        raise RuntimeError(classify_docker_failure(action, result.returncode, details))

    return result


def classify_docker_failure(action: str, returncode: int, details: str) -> str:
    """Turn Docker stderr into a more helpful user-facing message."""
    lower_details = details.lower()

    if "permission denied" in lower_details and "docker.sock" in lower_details:
        return (
            "Docker is installed, but this user cannot access the Docker daemon socket.\n"
            "Add your user to the docker group or use Docker Desktop with the right permissions,\n"
            "then sign in again and retry."
        )

    if (
        "cannot connect to the docker daemon" in lower_details
        or "is the docker daemon running" in lower_details
        or "open //./pipe/docker_engine" in lower_details
    ):
        return (
            "Docker is installed, but the daemon is not reachable.\n"
            "Start Docker Desktop or the Docker service, then try again."
        )

    if (
        "docker: 'compose' is not a docker command" in lower_details
        or "unknown command \"compose\"" in lower_details
        or "docker compose is not a docker command" in lower_details
    ):
        return (
            "Docker Compose is not available.\n"
            "Install the Docker Compose plugin (or docker-compose) and try again."
        )

    if details:
        return f"{action} failed (exit {returncode}).\n{details}"
    return f"{action} failed (exit {returncode})"
