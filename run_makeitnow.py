"""Run the locally installed MakeItNow CLI without activating a virtualenv."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent
    venv_dir = repo_root / ".makeitnow-venv"
    if sys.platform.startswith("win"):
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        python_executable = venv_dir / "bin" / "python"

    if not python_executable.exists():
        print(
            "[makeitnow] Local installation not found.\n"
            "[makeitnow] Run `python install.py` from the repo root first.",
            file=sys.stderr,
        )
        return 1

    args = argv if argv is not None else sys.argv[1:]
    result = subprocess.run([str(python_executable), "-m", "makeitnow.cli", *args])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
