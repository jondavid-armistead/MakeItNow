"""Clone a GitHub repository to a local directory."""

import subprocess
import tempfile
from pathlib import Path


def clone(repo_url: str, dest: Path | None = None) -> Path:
    """Clone *repo_url* into *dest* (or a new temp dir) and return the path.

    Raises RuntimeError if git exits non-zero.
    """
    if dest is None:
        dest = Path(tempfile.mkdtemp(prefix="makeitnow_"))

    result = subprocess.run(
        ["git", "clone", "--depth=1", repo_url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return dest


def short_sha(repo_dir: Path) -> str:
    """Return the short HEAD commit SHA of the cloned repo."""
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def repo_name_from_url(url: str) -> str:
    """Extract a sanitised repo name from a GitHub URL."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name.lower().replace(" ", "-")
