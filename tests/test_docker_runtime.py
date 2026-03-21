"""Tests for Docker runtime diagnostics."""

import subprocess

import pytest

from makeitnow.docker_runtime import (
    classify_docker_failure,
    ensure_compose_available,
    ensure_docker_access,
    find_compose_command,
)


def test_classify_permission_denied():
    message = classify_docker_failure(
        "docker compose up",
        1,
        "permission denied while trying to connect to the docker API at unix:///var/run/docker.sock",
    )
    assert "cannot access the Docker daemon socket" in message


def test_classify_daemon_unreachable():
    message = classify_docker_failure(
        "docker info",
        1,
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
    )
    assert "daemon is not reachable" in message


def test_find_compose_command_prefers_plugin(monkeypatch):
    monkeypatch.setattr("makeitnow.docker_runtime.shutil.which", lambda name: "/bin/docker")
    monkeypatch.setattr(
        "makeitnow.docker_runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    assert find_compose_command() == ["docker", "compose"]


def test_find_compose_command_falls_back_to_legacy_binary(monkeypatch):
    def fake_which(name: str):
        if name == "docker":
            return "/bin/docker"
        if name == "docker-compose":
            return "/bin/docker-compose"
        return None

    def fake_run(command, **kwargs):
        if command[:3] == ["docker", "compose", "version"]:
            return subprocess.CompletedProcess(command, 1, "", "compose missing")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("makeitnow.docker_runtime.shutil.which", fake_which)
    monkeypatch.setattr("makeitnow.docker_runtime.subprocess.run", fake_run)
    assert find_compose_command() == ["docker-compose"]


def test_ensure_compose_available_raises_when_missing(monkeypatch):
    monkeypatch.setattr("makeitnow.docker_runtime.find_compose_command", lambda: None)
    with pytest.raises(RuntimeError, match="Docker Compose is not available"):
        ensure_compose_available()


def test_ensure_docker_access_requires_binary(monkeypatch):
    monkeypatch.setattr("makeitnow.docker_runtime.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="Docker was not found on PATH"):
        ensure_docker_access()


def test_ensure_docker_access_reports_permission_issue(monkeypatch):
    monkeypatch.setattr("makeitnow.docker_runtime.shutil.which", lambda name: "/bin/docker")
    monkeypatch.setattr(
        "makeitnow.docker_runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            "",
            "permission denied while trying to connect to the docker API at unix:///var/run/docker.sock",
        ),
    )
    with pytest.raises(RuntimeError, match="cannot access the Docker daemon socket"):
        ensure_docker_access()
