"""Tests for compose helpers."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from makeitnow.compose import (
    ComposeRunResult,
    find_compose_file,
    format_compose_result,
    parse_compose_services,
    run_with_compose,
)
from makeitnow.docker_build import find_dockerfile


def test_find_compose_file_found(tmp_path: Path):
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    assert find_compose_file(tmp_path) == tmp_path / "docker-compose.yml"


def test_find_compose_file_yaml_extension(tmp_path: Path):
    (tmp_path / "docker-compose.yaml").write_text("version: '3'\n")
    assert find_compose_file(tmp_path) == tmp_path / "docker-compose.yaml"


def test_find_compose_file_missing(tmp_path: Path):
    assert find_compose_file(tmp_path) is None


def test_parse_compose_services_multiple_services_and_ports(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        textwrap.dedent(
            """\
            services:
              proxy:
                image: nginx
                ports:
                  - "8080:80"
              api:
                build: .
                ports:
                  - "${API_PORT}:3000"
              db:
                image: postgres
            """
        )
    )

    services = parse_compose_services(compose_file)

    assert [service.name for service in services] == ["proxy", "api", "db"]
    assert services[0].ports[0].host_port == 8080
    assert services[0].ports[0].container_port == 80
    assert services[1].ports[0].host_var == "API_PORT"
    assert services[1].ports[0].container_port == 3000
    assert services[2].ports == ()


def test_parse_compose_services_supports_long_syntax_and_defaults(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        textwrap.dedent(
            """\
            services:
              proxy:
                ports:
                  - target: 80
                    published: 8080
              web:
                ports:
                  - target: 443
                    published: ${WEB_TLS_PORT:-8443}
                    protocol: tcp
            """
        )
    )

    services = parse_compose_services(compose_file)

    assert services[0].ports[0].host_port == 8080
    assert services[1].ports[0].host_var == "WEB_TLS_PORT"
    assert services[1].ports[0].host_var_default == 8443
    assert services[1].ports[0].container_port == 443


def test_run_with_compose_validates_services_and_reports_all_urls(
    monkeypatch,
    tmp_path: Path,
):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        textwrap.dedent(
            """\
            services:
              proxy:
                image: nginx
                ports:
                  - "8080:80"
              api:
                image: my-api
                ports:
                  - "5000:5000"
              db:
                image: postgres
            """
        )
    )

    commands: list[tuple[str, ...]] = []

    def fake_run(command, **kwargs):
        commands.append(tuple(command))
        if command[-4:] == ["ps", "--services", "--status", "running"]:
            return subprocess.CompletedProcess(command, 0, "proxy\napi\ndb\n", "")
        if command[-3:] == ["port", "proxy", "80"]:
            return subprocess.CompletedProcess(command, 0, "0.0.0.0:8080\n", "")
        if command[-3:] == ["port", "api", "5000"]:
            return subprocess.CompletedProcess(command, 0, "0.0.0.0:5000\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("makeitnow.compose.ensure_compose_available", lambda: ["docker", "compose"])
    monkeypatch.setattr("makeitnow.compose.run_docker_command", fake_run)

    result = run_with_compose(tmp_path, compose_file, 8080)

    assert result.services == ("proxy", "api", "db")
    assert result.endpoints[0].service_name == "proxy"
    assert result.endpoints[0].host_port == 8080
    assert result.endpoints[1].service_name == "api"
    assert result.endpoints[1].host_port == 5000
    assert ("docker", "compose", "-f", str(compose_file), "up", "--build", "-d") in commands


def test_run_with_compose_allocates_variable_ports(monkeypatch, tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        textwrap.dedent(
            """\
            services:
              proxy:
                ports:
                  - "${PORT}:80"
              api:
                ports:
                  - "${API_PORT}:3000"
            """
        )
    )

    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run(command, **kwargs):
        calls.append((list(command), kwargs.get("env")))
        if command[-4:] == ["ps", "--services", "--status", "running"]:
            return subprocess.CompletedProcess(command, 0, "proxy\napi\n", "")
        if command[-3:] == ["port", "proxy", "80"]:
            return subprocess.CompletedProcess(command, 0, "0.0.0.0:8080\n", "")
        if command[-3:] == ["port", "api", "3000"]:
            return subprocess.CompletedProcess(command, 0, "0.0.0.0:8081\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("makeitnow.compose.ensure_compose_available", lambda: ["docker", "compose"])
    monkeypatch.setattr("makeitnow.compose.find_free_port", lambda start=8080: start)
    monkeypatch.setattr("makeitnow.compose.run_docker_command", fake_run)

    result = run_with_compose(tmp_path, compose_file, 8080)

    up_call = next(call for call in calls if call[0][-3:] == ["up", "--build", "-d"])
    assert up_call[1] is not None
    assert up_call[1]["PORT"] == "8080"
    assert up_call[1]["API_PORT"] == "8081"
    assert [endpoint.host_port for endpoint in result.endpoints] == [8080, 8081]


def test_format_compose_result_lists_all_urls():
    result = ComposeRunResult(
        services=("proxy", "api"),
        endpoints=(
            type("Endpoint", (), {"service_name": "proxy", "host_port": 8080, "container_port": 80, "protocol": "tcp"})(),
            type("Endpoint", (), {"service_name": "api", "host_port": 5000, "container_port": 5000, "protocol": "tcp"})(),
        ),
    )

    summary = format_compose_result(result)

    assert "proxy: http://localhost:8080" in summary
    assert "api: http://localhost:5000" in summary


def test_find_dockerfile_at_root(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    assert find_dockerfile(tmp_path) == tmp_path / "Dockerfile"


def test_find_dockerfile_nested(tmp_path: Path):
    sub = tmp_path / "app"
    sub.mkdir()
    (sub / "Dockerfile").write_text("FROM scratch\n")
    assert find_dockerfile(tmp_path) == sub / "Dockerfile"


def test_find_dockerfile_missing(tmp_path: Path):
    assert find_dockerfile(tmp_path) is None
