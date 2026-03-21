"""Tests for repo-local uninstall helpers."""

from pathlib import Path

from makeitnow.uninstaller import build_uninstall_plan, run_uninstall


def test_build_uninstall_plan_targets_expected_artifacts(tmp_path: Path):
    venv_dir = tmp_path / ".makeitnow-venv"
    venv_dir.mkdir()
    (tmp_path / "install.py").write_text("print('install')\n")
    (tmp_path / "run_makeitnow.py").write_text("print('run')\n")

    plan = build_uninstall_plan(tmp_path)
    targets = {target.path.name: target for target in plan.targets}

    assert targets[".makeitnow-venv"].exists is True
    assert targets["install.py"].exists is True
    assert targets["run_makeitnow.py"].exists is True
    assert "Docker" in plan.untouched_items


def test_run_uninstall_removes_only_managed_artifacts(tmp_path: Path):
    venv_dir = tmp_path / ".makeitnow-venv"
    venv_dir.mkdir()
    (venv_dir / "marker.txt").write_text("venv\n")
    (tmp_path / "install.py").write_text("print('install')\n")
    (tmp_path / "run_makeitnow.py").write_text("print('run')\n")
    unrelated = tmp_path / "keep-me.txt"
    unrelated.write_text("keep\n")

    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        messages.append(prompt)
        return "y"

    result = run_uninstall(
        tmp_path,
        input_func=fake_input,
        print_func=messages.append,
    )

    assert result == 0
    assert not venv_dir.exists()
    assert not (tmp_path / "install.py").exists()
    assert not (tmp_path / "run_makeitnow.py").exists()
    assert unrelated.exists()
    assert any("Remove these artifacts now?" in message for message in messages)
    assert any("Installer entry script" in message for message in messages)


def test_run_uninstall_cancel_leaves_files(tmp_path: Path):
    venv_dir = tmp_path / ".makeitnow-venv"
    venv_dir.mkdir()
    install_script = tmp_path / "install.py"
    launcher = tmp_path / "run_makeitnow.py"
    install_script.write_text("print('install')\n")
    launcher.write_text("print('run')\n")

    result = run_uninstall(
        tmp_path,
        input_func=lambda prompt: "n",
        print_func=lambda message: None,
    )

    assert result == 1
    assert venv_dir.exists()
    assert install_script.exists()
    assert launcher.exists()
