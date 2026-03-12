"""Build a Docker image from a cloned repository."""

import subprocess
from pathlib import Path


def find_dockerfile(repo_dir: Path) -> Path | None:
    """Return the path to a Dockerfile in *repo_dir*, or None if not found.

    Checks the root first, then one level deep.
    """
    for candidate in [
        repo_dir / "Dockerfile",
        repo_dir / "dockerfile",
        *repo_dir.glob("*/Dockerfile"),
        *repo_dir.glob("*/dockerfile"),
    ]:
        if candidate.is_file():
            return candidate
    return None


def build_image(repo_dir: Path, tag: str) -> str:
    """Build a Docker image from *repo_dir* and tag it *tag*.

    Returns the image tag on success.
    Raises RuntimeError if the build fails or no Dockerfile is found.
    """
    dockerfile = find_dockerfile(repo_dir)
    if dockerfile is None:
        raise RuntimeError(
            f"No Dockerfile found in {repo_dir}. "
            "MakeItNow requires a Dockerfile to build the image."
        )

    context_dir = dockerfile.parent
    result = subprocess.run(
        ["docker", "build", "-t", tag, "-f", str(dockerfile), str(context_dir)],
        capture_output=False,  # stream output so user sees build progress
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker build failed (exit {result.returncode})")
    return tag
