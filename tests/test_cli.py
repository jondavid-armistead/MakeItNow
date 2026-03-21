"""Tests for CLI entrypoint wiring."""

from pathlib import Path

import pytest

from makeitnow.cli import main


def test_cli_exports_main():
    assert callable(main)


def test_build_env_file_prompts_for_optional_and_required(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("makeitnow.cli.scan_env_vars", lambda repo_dir: {"DATABASE_URL", "LOG_LEVEL"})
    inputs = iter(["y", "postgres://db", "debug"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    from makeitnow.cli import _build_env_file

    _build_env_file(tmp_path)

    assert (tmp_path / ".env").read_text() == "DATABASE_URL=postgres://db\nLOG_LEVEL=debug\n"


def test_cli_stop_command_uses_runtime_control(monkeypatch, capsys):
    monkeypatch.setattr(
        "makeitnow.cli.stop_makeitnow_services",
        lambda: type(
            "StopResult",
            (),
            {
                "removed_containers": ("makeitnow-demo",),
                "removed_images": (),
                "removed_tmp_dirs": (),
                "warnings": (),
            },
        )(),
    )
    monkeypatch.setattr(
        "makeitnow.cli.format_stop_result",
        lambda result: "[makeitnow] Stop complete.\n  - makeitnow-demo",
    )

    main(["stop"])

    assert "Stop complete" in capsys.readouterr().out
