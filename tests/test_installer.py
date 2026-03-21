"""Tests for installer planning helpers."""

from pathlib import Path

import subprocess

from makeitnow.installer import (
    InstallAction,
    build_install_plan,
    format_completion_summary,
    run_install,
)


def test_build_install_plan_for_linux_apt(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("makeitnow.installer.sys.platform", "linux")

    def fake_which(name: str):
        mapping = {
            "apt-get": "/usr/bin/apt-get",
            "docker": None,
            "docker-compose": None,
            "git": None,
            "winget": None,
            "brew": None,
            "dnf": None,
            "yum": None,
            "pacman": None,
            "zypper": None,
        }
        return mapping.get(name)

    monkeypatch.setattr("makeitnow.installer.shutil.which", fake_which)
    monkeypatch.setattr("makeitnow.installer.find_compose_command", lambda: None)

    plan = build_install_plan(tmp_path)

    assert plan.platform_label == "Linux"
    commands = [action.command for action in plan.actions]
    assert ("sudo", "apt-get", "update") in commands
    assert ("sudo", "apt-get", "install", "-y", "docker.io", "docker-compose-v2") in commands
    assert ("sudo", "apt-get", "install", "-y", "git") in commands


def test_build_install_plan_for_windows(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("makeitnow.installer.sys.platform", "win32")

    def fake_which(name: str):
        mapping = {
            "winget": "C:/Windows/System32/winget.exe",
            "docker": None,
            "docker-compose": None,
            "git": None,
            "brew": None,
        }
        return mapping.get(name)

    monkeypatch.setattr("makeitnow.installer.shutil.which", fake_which)
    monkeypatch.setattr("makeitnow.installer.find_compose_command", lambda: None)

    plan = build_install_plan(tmp_path)

    assert plan.platform_label == "Windows"
    commands = [action.command for action in plan.actions]
    assert ("winget", "install", "-e", "--id", "Docker.DockerDesktop") in commands
    assert ("winget", "install", "-e", "--id", "Git.Git") in commands


def test_completion_summary_includes_launcher(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("makeitnow.installer.sys.platform", "linux")
    monkeypatch.setattr("makeitnow.installer.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr(
        "makeitnow.installer.find_compose_command",
        lambda: ["docker", "compose"],
    )

    plan = build_install_plan(tmp_path)
    summary = format_completion_summary(
        plan,
        completed_requirements=("Docker",),
        completed_actions=(
            InstallAction(
                label="Install Docker Desktop",
                command=("winget", "install", "-e", "--id", "Docker.DockerDesktop"),
                packages=("Docker Desktop",),
            ),
        ),
    )

    assert "python run_makeitnow.py https://github.com/org/my-app" in summary
    assert "Quick start" in summary
    assert "Dependency installed: Docker" in summary
    assert "Docker Desktop" in summary


def test_run_install_prompts_per_dependency(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("makeitnow.installer.sys.platform", "linux")

    def fake_which(name: str):
        mapping = {
            "apt-get": "/usr/bin/apt-get",
            "docker": None,
            "docker-compose": None,
            "git": None,
            "winget": None,
            "brew": None,
            "dnf": None,
            "yum": None,
            "pacman": None,
            "zypper": None,
        }
        return mapping.get(name)

    commands_run: list[tuple[str, ...]] = []
    messages: list[str] = []
    answers = iter(["y", "n"])

    monkeypatch.setattr("makeitnow.installer.shutil.which", fake_which)
    monkeypatch.setattr("makeitnow.installer.find_compose_command", lambda: None)
    monkeypatch.setattr(
        "makeitnow.installer.subprocess.run",
        lambda command, **kwargs: (
            commands_run.append(tuple(command))
            or subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    monkeypatch.setattr(
        "makeitnow.installer._install_package",
        lambda repo_root, print_func=print: messages.append("package-installed"),
    )

    def fake_input(prompt: str) -> str:
        messages.append(prompt)
        return next(answers)

    result = run_install(
        tmp_path,
        input_func=fake_input,
        print_func=messages.append,
    )

    assert result == 0
    assert ("sudo", "apt-get", "update") in commands_run
    assert ("sudo", "apt-get", "install", "-y", "docker.io", "docker-compose-v2") in commands_run
    assert ("sudo", "apt-get", "install", "-y", "git") not in commands_run
    assert any("Install Docker now?" in message for message in messages)
    assert any("Install Git now?" in message for message in messages)
