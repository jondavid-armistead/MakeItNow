"""Tests for runtime stop/cleanup helpers."""

from pathlib import Path

from makeitnow.runtime_control import format_stop_result, stop_makeitnow_services


def test_stop_makeitnow_services_removes_containers_images_and_tmp_dirs(monkeypatch, tmp_path: Path):
    tmp_dir = tmp_path / "makeitnow_demo"
    tmp_dir.mkdir()
    (tmp_dir / "file.txt").write_text("demo\n")

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        if command[:3] == ["docker", "ps", "-a"]:
            return type("Result", (), {"stdout": "abc123\tmakeitnow:demo\tmakeitnow-demo\n"})()
        return type("Result", (), {"stdout": ""})()

    monkeypatch.setattr("makeitnow.runtime_control.run_docker_command", fake_run)
    monkeypatch.setattr("makeitnow.runtime_control.tempfile.gettempdir", lambda: str(tmp_path))

    result = stop_makeitnow_services()

    assert result.removed_containers == ("makeitnow-demo",)
    assert result.removed_images == ("makeitnow:demo",)
    assert str(tmp_dir) in result.removed_tmp_dirs
    assert ["docker", "rm", "-f", "abc123"] in commands
    assert ["docker", "image", "rm", "makeitnow:demo"] in commands


def test_format_stop_result_includes_summary():
    result = type(
        "StopResult",
        (),
        {
            "removed_containers": ("makeitnow-demo",),
            "removed_images": ("makeitnow:demo",),
            "removed_tmp_dirs": ("/tmp/makeitnow_demo",),
            "warnings": ("image still in use",),
        },
    )()

    summary = format_stop_result(result)

    assert "Removed containers" in summary
    assert "makeitnow-demo" in summary
    assert "image still in use" in summary
