"""Run a Docker image via Compose or plain docker run."""

import re
import subprocess
from pathlib import Path


_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def find_compose_file(repo_dir: Path) -> Path | None:
    for name in _COMPOSE_FILES:
        candidate = repo_dir / name
        if candidate.is_file():
            return candidate
    return None


def _exposed_container_port(compose_file: Path) -> int:
    """Best-effort parse of the first ports mapping in a compose file.

    Returns the container-side port number, or 80 as a fallback.
    """
    text = compose_file.read_text(errors="replace")
    # Match patterns like "- 80" / "- 8080:80" / "- '8080:80'"
    match = re.search(r"ports:[^\n]*\n\s+-\s+['\"]?(?:\d+:)?(\d+)['\"]?", text)
    if match:
        return int(match.group(1))
    return 80


def run_with_compose(repo_dir: Path, compose_file: Path, host_port: int) -> None:
    """Start services defined in *compose_file*, mapping the first exposed port to *host_port*."""
    container_port = _exposed_container_port(compose_file)
    env_override = {
        "PORT": str(host_port),
    }
    result = subprocess.run(
        [
            "docker", "compose",
            "-f", str(compose_file),
            "up", "--build", "-d",
            "--scale", f"app=1",
        ],
        cwd=str(repo_dir),
        env={**_base_env(), **env_override},
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed (exit {result.returncode})")


def run_with_docker(image_tag: str, host_port: int, container_port: int = 80) -> None:
    """Run *image_tag* mapping *host_port* → *container_port*."""
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--restart=unless-stopped",
            "-p", f"{host_port}:{container_port}",
            "--name", _safe_name(image_tag),
            image_tag,
        ],
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed (exit {result.returncode})")


def _safe_name(tag: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", tag)


def _base_env() -> dict:
    import os
    return dict(os.environ)
