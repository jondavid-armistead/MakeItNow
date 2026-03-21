"""Lifecycle management for MakeItNow-managed Docker resources."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from makeitnow.docker_runtime import run_docker_command


@dataclass(frozen=True)
class ManagedContainer:
    container_id: str
    image: str
    name: str


@dataclass(frozen=True)
class StopResult:
    removed_containers: tuple[str, ...]
    removed_images: tuple[str, ...]
    removed_tmp_dirs: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def stop_makeitnow_services() -> StopResult:
    """Stop/remove MakeItNow-managed containers, images, and temp directories."""
    warnings: list[str] = []
    containers = _list_managed_containers()
    removed_containers: list[str] = []
    removed_images: list[str] = []

    if containers:
        container_ids = [container.container_id for container in containers]
        run_docker_command(
            ["docker", "rm", "-f", *container_ids],
            action="docker rm",
            capture_output=True,
        )
        removed_containers.extend(container.name for container in containers)

        for image in sorted({container.image for container in containers if container.image}):
            try:
                run_docker_command(
                    ["docker", "image", "rm", image],
                    action="docker image rm",
                    capture_output=True,
                )
            except RuntimeError as exc:
                warnings.append(str(exc))
                continue
            removed_images.append(image)

    removed_tmp_dirs = _cleanup_tmp_dirs()
    return StopResult(
        removed_containers=tuple(removed_containers),
        removed_images=tuple(removed_images),
        removed_tmp_dirs=tuple(removed_tmp_dirs),
        warnings=tuple(warnings),
    )


def format_stop_result(result: StopResult) -> str:
    """Render the stop/cleanup summary."""
    lines = ["[makeitnow] Stop complete."]
    if result.removed_containers:
        lines.append("[makeitnow] Removed containers:")
        for name in result.removed_containers:
            lines.append(f"  - {name}")
    if result.removed_images:
        lines.append("[makeitnow] Removed images:")
        for image in result.removed_images:
            lines.append(f"  - {image}")
    if result.removed_tmp_dirs:
        lines.append("[makeitnow] Removed temp directories:")
        for directory in result.removed_tmp_dirs:
            lines.append(f"  - {directory}")
    if not (result.removed_containers or result.removed_images or result.removed_tmp_dirs):
        lines.append("[makeitnow] No MakeItNow-managed containers or temp directories were found.")
    for warning in result.warnings:
        lines.append(f"[makeitnow] Warning: {warning}")
    return "\n".join(lines)


def _list_managed_containers() -> tuple[ManagedContainer, ...]:
    try:
        result = run_docker_command(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=makeitnow-",
                "--format",
                "{{.ID}}\t{{.Image}}\t{{.Names}}",
            ],
            action="docker ps",
            capture_output=True,
        )
    except RuntimeError:
        return ()

    containers: list[ManagedContainer] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        container_id, image, name = line.split("\t", 2)
        containers.append(
            ManagedContainer(
                container_id=container_id,
                image=image,
                name=name,
            )
        )
    return tuple(containers)


def _cleanup_tmp_dirs() -> list[str]:
    tmp_root = Path(tempfile.gettempdir())
    removed: list[str] = []
    for candidate in tmp_root.glob("makeitnow_*"):
        if not candidate.exists():
            continue
        if candidate.is_dir():
            for child in candidate.rglob("*"):
                if child.is_file():
                    child.unlink()
            for child in sorted(candidate.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            candidate.rmdir()
        else:
            candidate.unlink()
        removed.append(str(candidate))
    return removed
