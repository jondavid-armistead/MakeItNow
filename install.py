"""Repo-local installer entrypoint for MakeItNow."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from makeitnow.installer import main


if __name__ == "__main__":
    main()
