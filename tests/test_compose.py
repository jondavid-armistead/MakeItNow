"""Tests for compose helpers."""

import textwrap
from pathlib import Path

import pytest

from makeitnow.compose import find_compose_file, _exposed_container_port
from makeitnow.docker_build import find_dockerfile


def test_find_compose_file_found(tmp_path: Path):
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    assert find_compose_file(tmp_path) == tmp_path / "docker-compose.yml"


def test_find_compose_file_yaml_extension(tmp_path: Path):
    (tmp_path / "docker-compose.yaml").write_text("version: '3'\n")
    assert find_compose_file(tmp_path) == tmp_path / "docker-compose.yaml"


def test_find_compose_file_missing(tmp_path: Path):
    assert find_compose_file(tmp_path) is None


def test_exposed_container_port_parses_mapping(tmp_path: Path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(textwrap.dedent("""\
        services:
          app:
            ports:
              - "3000:3000"
    """))
    assert _exposed_container_port(f) == 3000


def test_exposed_container_port_fallback(tmp_path: Path):
    f = tmp_path / "docker-compose.yml"
    f.write_text("services:\n  app:\n    image: nginx\n")
    assert _exposed_container_port(f) == 80


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
