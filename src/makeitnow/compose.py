"""Run Docker Compose services and inspect their published endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from makeitnow.docker_runtime import ensure_compose_available, run_docker_command
from makeitnow.ports import find_free_port

_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
_PORT_VAR_RE = re.compile(r"^\$\{([A-Z0-9_]+)(?:(?::-?)([^}]+))?\}$")


@dataclass(frozen=True)
class ComposePort:
    container_port: int
    host_port: int | None = None
    host_var: str | None = None
    host_var_default: int | None = None
    protocol: str = "tcp"


@dataclass(frozen=True)
class ComposeService:
    name: str
    ports: tuple[ComposePort, ...] = ()


@dataclass(frozen=True)
class ComposeEndpoint:
    service_name: str
    host_port: int
    container_port: int
    protocol: str = "tcp"


@dataclass(frozen=True)
class ComposeRunResult:
    services: tuple[str, ...]
    endpoints: tuple[ComposeEndpoint, ...]
    failed_services: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def find_compose_file(repo_dir: Path) -> Path | None:
    for name in _COMPOSE_FILES:
        candidate = repo_dir / name
        if candidate.is_file():
            return candidate
    return None


def parse_compose_services(compose_file: Path) -> tuple[ComposeService, ...]:
    """Best-effort parse of services and published ports from a Compose file."""
    services: list[ComposeService] = []
    current_name: str | None = None
    current_ports: list[ComposePort] = []
    current_long_port: dict[str, str] | None = None
    services_indent: int | None = None
    ports_indent: int | None = None

    def flush_long_port() -> None:
        nonlocal current_long_port, current_ports
        if current_long_port is None:
            return
        port = _parse_long_port_mapping(current_long_port)
        if port is not None:
            current_ports.append(port)
        current_long_port = None

    def flush_service() -> None:
        nonlocal current_name, current_ports, ports_indent
        flush_long_port()
        if current_name is not None:
            services.append(ComposeService(name=current_name, ports=tuple(current_ports)))
        current_name = None
        current_ports = []
        ports_indent = None

    for raw_line in compose_file.read_text(errors="replace").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        stripped = raw_line.lstrip()
        indent = len(raw_line) - len(stripped)

        if services_indent is None:
            if stripped == "services:":
                services_indent = indent
            continue

        if indent <= services_indent and not stripped.startswith("- "):
            flush_service()
            services_indent = None
            if stripped == "services:":
                services_indent = indent
            continue

        if indent == services_indent + 2 and stripped.endswith(":"):
            flush_service()
            current_name = stripped[:-1].strip().strip("'\"")
            continue

        if current_name is None:
            continue

        if indent == services_indent + 4 and stripped == "ports:":
            flush_long_port()
            ports_indent = indent
            continue

        if ports_indent is None:
            continue

        if indent <= ports_indent:
            flush_long_port()
            ports_indent = None
            continue

        if stripped.startswith("- "):
            flush_long_port()
            item = stripped[2:].strip()
            if not item:
                current_long_port = {}
                continue
            if _looks_like_short_port_entry(item):
                port = _parse_short_port_mapping(item)
                if port is not None:
                    current_ports.append(port)
                continue
            current_long_port = _parse_mapping_pair(item)
            continue

        if current_long_port is not None:
            pair = _parse_mapping_pair(stripped)
            current_long_port.update(pair)

    flush_service()
    return tuple(services)


def format_compose_result(result: ComposeRunResult) -> str:
    """Render the final user-facing summary for a compose run."""
    lines: list[str] = []
    if result.services:
        lines.append("[makeitnow] ✓ Running compose services: " + ", ".join(result.services))
    else:
        lines.append("[makeitnow] No compose services are currently running.")

    if result.endpoints:
        lines.append("[makeitnow] Reachable URLs:")
        for endpoint in result.endpoints:
            lines.append(
                f"  - {endpoint.service_name}: http://127.0.0.1:{endpoint.host_port}"
                f" (container {endpoint.container_port}/{endpoint.protocol})"
            )
    if result.failed_services:
        lines.append(
            "[makeitnow] Warning: services not running: "
            + ", ".join(result.failed_services)
        )
    for warning in result.warnings:
        lines.append(f"[makeitnow] Warning: {warning}")
    return "\n".join(lines)


def run_with_compose(
    repo_dir: Path,
    compose_file: Path,
    port_start: int,
    *,
    project_name: str | None = None,
) -> ComposeRunResult:
    """Start services defined in *compose_file* and validate published endpoints."""
    compose_command = ensure_compose_available()
    services = parse_compose_services(compose_file)
    env_override = _allocate_port_overrides(services, start=port_start)
    env = {**_base_env(), **env_override}
    command_prefix = _compose_command(compose_command, compose_file, project_name)
    startup_warning: str | None = None

    try:
        run_docker_command(
            [
                *command_prefix,
                "up",
                "--build",
                "-d",
            ],
            action="docker compose up",
            cwd=str(repo_dir),
            env=env,
        )
    except RuntimeError as exc:
        startup_warning = str(exc)

    declared_service_names = tuple(service.name for service in services)
    running_services = _running_services(repo_dir, command_prefix, env)
    if startup_warning is not None and not running_services:
        raise RuntimeError(startup_warning)

    failed_services = tuple(
        service_name
        for service_name in declared_service_names
        if service_name not in running_services
    )
    endpoints, warnings = _resolve_endpoints(
        repo_dir,
        command_prefix,
        services,
        running_services,
        env,
    )
    if startup_warning is not None:
        warnings.append(startup_warning)
    return ComposeRunResult(
        services=running_services,
        endpoints=endpoints,
        failed_services=failed_services,
        warnings=tuple(warnings),
    )


def run_with_docker(image_tag: str, host_port: int, container_port: int = 80) -> None:
    """Run *image_tag* mapping *host_port* → *container_port*."""
    run_docker_command(
        [
            "docker",
            "run",
            "-d",
            "--restart=unless-stopped",
            "-p",
            f"{host_port}:{container_port}",
            "--name",
            _safe_name(f"makeitnow-{image_tag}"),
            "--label",
            "makeitnow.managed=true",
            image_tag,
        ],
        action="docker run",
    )


def _running_services(
    repo_dir: Path,
    command_prefix: list[str],
    env: dict[str, str],
) -> tuple[str, ...]:
    result = run_docker_command(
        [
            *command_prefix,
            "ps",
            "--services",
            "--status",
            "running",
        ],
        action="docker compose ps",
        cwd=str(repo_dir),
        env=env,
        capture_output=True,
    )
    return tuple(
        line.strip()
        for line in (result.stdout or "").splitlines()
        if line.strip()
    )


def _resolve_endpoints(
    repo_dir: Path,
    command_prefix: list[str],
    services: tuple[ComposeService, ...],
    running_services: tuple[str, ...],
    env: dict[str, str],
) -> tuple[tuple[ComposeEndpoint, ...], list[str]]:
    endpoints: list[ComposeEndpoint] = []
    warnings: list[str] = []
    running = set(running_services)
    seen: set[tuple[str, int, str]] = set()
    for service in services:
        if service.name not in running:
            continue
        for port in service.ports:
            key = (service.name, port.container_port, port.protocol)
            if key in seen:
                continue
            seen.add(key)

            published_port = _query_published_port(repo_dir, command_prefix, service.name, port.container_port, env)
            if published_port is None:
                warnings.append(
                    f"Expected compose service {service.name} to publish container port "
                    f"{port.container_port}/{port.protocol}, but no published host port was found."
                )
                continue

            expected_port = _expected_host_port(port, env)
            if expected_port is not None and published_port != expected_port:
                warnings.append(
                    f"Compose service {service.name} published localhost:{published_port}, "
                    f"but the compose configuration expected localhost:{expected_port}."
                )

            endpoints.append(
                ComposeEndpoint(
                    service_name=service.name,
                    host_port=published_port,
                    container_port=port.container_port,
                    protocol=port.protocol,
                )
            )
    return tuple(endpoints), warnings


def _query_published_port(
    repo_dir: Path,
    command_prefix: list[str],
    service_name: str,
    container_port: int,
    env: dict[str, str],
) -> int | None:
    try:
        result = run_docker_command(
            [
                *command_prefix,
                "port",
                service_name,
                str(container_port),
            ],
            action="docker compose port",
            cwd=str(repo_dir),
            env=env,
            capture_output=True,
        )
    except RuntimeError:
        return None
    outputs = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if not outputs:
        return None

    match = re.search(r":(\d+)$", outputs[0])
    if match is None:
        return None
    return int(match.group(1))


def _allocate_port_overrides(
    services: tuple[ComposeService, ...],
    *,
    start: int,
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    next_start = start
    for service in services:
        for port in service.ports:
            if (
                port.host_var is None
                or port.host_var in overrides
                or port.host_port is not None
                or port.host_var_default is not None
            ):
                continue
            assigned_port = find_free_port(start=next_start)
            overrides[port.host_var] = str(assigned_port)
            next_start = assigned_port + 1
    return overrides


def _expected_host_port(port: ComposePort, env: dict[str, str]) -> int | None:
    if port.host_port is not None:
        return port.host_port
    if port.host_var is not None and port.host_var in env and env[port.host_var].isdigit():
        return int(env[port.host_var])
    if port.host_var_default is not None:
        return port.host_var_default
    return None


def _compose_command(
    compose_command: list[str],
    compose_file: Path,
    project_name: str | None,
) -> list[str]:
    command = [*compose_command]
    if project_name:
        command.extend(["-p", project_name])
    command.extend(["-f", str(compose_file)])
    return command


def _looks_like_short_port_entry(item: str) -> bool:
    stripped = item.strip().strip("'\"")
    return bool(stripped) and (
        stripped[0].isdigit()
        or stripped[0] == "$"
        or stripped.startswith("localhost:")
        or stripped.startswith("127.0.0.1:")
        or stripped.startswith("0.0.0.0:")
    )


def _parse_mapping_pair(text: str) -> dict[str, str]:
    key, value = text.split(":", 1)
    return {key.strip(): value.strip().strip("'\"")}


def _parse_short_port_mapping(text: str) -> ComposePort | None:
    cleaned = text.strip().strip("'\"")
    protocol = "tcp"
    if "/" in cleaned:
        cleaned, protocol = cleaned.rsplit("/", 1)

    parts = cleaned.split(":")
    if len(parts) == 1:
        container_port = _parse_numeric_port(parts[0])
        if container_port is None:
            return None
        return ComposePort(container_port=container_port, protocol=protocol)

    if len(parts) == 2:
        host_spec, container_spec = parts
    else:
        host_spec, container_spec = parts[-2], parts[-1]

    container_port = _parse_numeric_port(container_spec)
    if container_port is None:
        return None

    host_port = _parse_numeric_port(host_spec)
    host_var, host_var_default = _parse_port_variable(host_spec)
    return ComposePort(
        container_port=container_port,
        host_port=host_port,
        host_var=host_var,
        host_var_default=host_var_default,
        protocol=protocol,
    )


def _parse_long_port_mapping(mapping: dict[str, str]) -> ComposePort | None:
    container_port = _parse_numeric_port(mapping.get("target"))
    if container_port is None:
        return None
    host_port = _parse_numeric_port(mapping.get("published"))
    host_var, host_var_default = _parse_port_variable(mapping.get("published"))
    protocol = mapping.get("protocol", "tcp")
    return ComposePort(
        container_port=container_port,
        host_port=host_port,
        host_var=host_var,
        host_var_default=host_var_default,
        protocol=protocol,
    )


def _parse_numeric_port(value: str | None) -> int | None:
    if value is None:
        return None
    candidate = value.strip().strip("'\"")
    if candidate.isdigit():
        return int(candidate)
    return None


def _parse_port_variable(value: str | None) -> tuple[str | None, int | None]:
    if value is None:
        return None, None
    match = _PORT_VAR_RE.match(value.strip().strip("'\""))
    if match is None:
        return None, None
    default_port = _parse_numeric_port(match.group(2))
    return match.group(1), default_port


def _base_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def _safe_name(tag: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", tag)
