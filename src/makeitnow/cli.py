"""MakeItNow CLI — the main entry point."""

import argparse
import shutil
import sys
from pathlib import Path

from makeitnow.clone import clone, repo_name_from_url, short_sha
from makeitnow.docker_build import build_image, find_dockerfile
from makeitnow.ports import find_free_port
from makeitnow.compose import find_compose_file, run_with_compose, run_with_docker


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


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

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

    compose_file = find_compose_file(repo_dir)
    host_port = find_free_port(start=args.port_start)

    try:
        if compose_file:
            print(f"[makeitnow] Found {compose_file.name} — using docker compose")
            print(f"[makeitnow] Building and starting services on port {host_port} …")
            run_with_compose(repo_dir, compose_file, host_port)
        else:
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

    print(f"\n[makeitnow] ✓ Running at http://localhost:{host_port}")


if __name__ == "__main__":
    main()
