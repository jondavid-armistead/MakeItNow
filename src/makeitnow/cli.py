"""MakeItNow CLI — the main entry point."""

import argparse
import shutil
import sys
from pathlib import Path

from makeitnow.clone import clone, repo_name_from_url, short_sha
from makeitnow.docker_build import build_image, find_dockerfile
from makeitnow.compose import (
    ComposeRunResult,
    find_compose_file,
    format_compose_result,
    run_with_compose,
    run_with_docker,
)
from makeitnow.docker_runtime import ensure_docker_access
from makeitnow.env_scan import scan_env_vars, is_required
from makeitnow.ports import find_free_port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="makeitnow",
        description=(
            "Clone a GitHub repo, build its Docker image, "
            "and run it on an available local port."
        ),
    )
    parser.add_argument("repo_url", help="GitHub repository URL to clone and run")
    parser.add_argument(
        "--port-start",
        type=int,
        default=8080,
        metavar="PORT",
        help="First port to try when scanning for a free port (default: 8080)",
    )
    parser.add_argument(
        "--container-port",
        type=int,
        default=None,
        metavar="PORT",
        help="Container-side port to map (default: auto-detect from Compose file or 80)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the cloned repo directory after running",
    )
    parser.add_argument(
        "--clone-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Clone repo into this directory (implies --keep)",
    )
    return parser


def _build_env_file(repo_dir: Path) -> None:
    """Scan repo for env var references, prompt the user, and write a .env file."""
    print("[makeitnow] Scanning for environment variables…")
    found = scan_env_vars(repo_dir)

    env_path = repo_dir / ".env"

    if not found:
        env_path.touch()
        return

    required = sorted(v for v in found if is_required(v))
    optional = sorted(v for v in found if not is_required(v))
    all_vars = required + optional

    print(f"\n[makeitnow] Found {len(all_vars)} environment variable(s) referenced in this repo:\n")
    for v in required:
        print(f"  {v}=  \033[33m(required)\033[0m")
    for v in optional:
        print(f"  {v}=")
    print()

    try:
        answer = input("[makeitnow] Create .env with these variables? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        env_path.touch()
        return

    if answer in ("n", "no"):
        env_path.touch()
        return

    values: dict[str, str] = {}

    if required:
        print("\n[makeitnow] Enter values for required variables (press Enter to skip):")
        for v in required:
            try:
                val = input(f"  {v}: ").strip()
            except (EOFError, KeyboardInterrupt):
                val = ""
                print()
            if not val:
                print(
                    f"  \033[33m⚠  {v} left blank — the container may not function correctly without it.\033[0m",
                    file=sys.stderr,
                )
            values[v] = val

    lines = [f"{v}={values.get(v, '')}" for v in all_vars]
    env_path.write_text("\n".join(lines) + "\n")

    print(f"\n[makeitnow] Created .env ({len(all_vars)} variable(s)):")
    print("─" * 40)
    for line in lines:
        print(f"  {line}")
    print("─" * 40)
    print()


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint used by the console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not shutil.which("git"):
        print(
            "[makeitnow] ERROR: git not found on PATH.\n"
            "  Install Git and try again: https://git-scm.com/downloads",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        ensure_docker_access()
    except RuntimeError as exc:
        print(f"[makeitnow] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    repo_url: str = args.repo_url
    keep: bool = args.keep or args.clone_dir is not None

    print(f"[makeitnow] Cloning {repo_url} …")
    try:
        repo_dir = clone(repo_url, dest=args.clone_dir)
    except RuntimeError as exc:
        print(f"[makeitnow] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    repo_name = repo_name_from_url(repo_url)
    sha = short_sha(repo_dir)
    image_tag = f"{repo_name}:{sha}"

    print(f"[makeitnow] Cloned to {repo_dir}")

    _build_env_file(repo_dir)

    compose_file = find_compose_file(repo_dir)
    compose_result: ComposeRunResult | None = None

    try:
        if compose_file:
            print(f"[makeitnow] Found {compose_file.name} — using docker compose")
            print("[makeitnow] Building and starting compose services …")
            compose_result = run_with_compose(repo_dir, compose_file, args.port_start)
        else:
            host_port = find_free_port(start=args.port_start)
            dockerfile = find_dockerfile(repo_dir)
            if dockerfile is None:
                print(
                    "[makeitnow] ERROR: No Dockerfile or docker-compose file found in repo.",
                    file=sys.stderr,
                )
                sys.exit(1)

            print(f"[makeitnow] Building Docker image {image_tag} …")
            build_image(repo_dir, image_tag)

            container_port = args.container_port or 80
            print(f"[makeitnow] Running container on port {host_port} …")
            run_with_docker(image_tag, host_port, container_port)

    except RuntimeError as exc:
        print(f"[makeitnow] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if not keep:
            shutil.rmtree(repo_dir, ignore_errors=True)

    if compose_result is not None:
        print()
        print(format_compose_result(compose_result))
    else:
        print(f"\n[makeitnow] ✓ Running at http://localhost:{host_port}")


if __name__ == "__main__":
    main()
