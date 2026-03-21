"""Tests for env_scan module."""

import textwrap
from pathlib import Path

import pytest

from makeitnow.env_scan import is_required, scan_env_vars


# ---------------------------------------------------------------------------
# is_required heuristic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("var", [
    "DATABASE_URL", "REDIS_URL", "API_KEY", "STRIPE_SECRET_KEY",
    "JWT_SECRET", "AWS_ACCESS_KEY", "SMTP_PASSWORD", "DB_PASS",
    "PRIVATE_KEY", "AUTH_TOKEN", "ENCRYPTION_KEY", "WEBHOOK_SECRET",
    "DB_HOST", "DB_USER", "SSL_CERT",
])
def test_is_required_true(var: str):
    assert is_required(var) is True


@pytest.mark.parametrize("var", [
    "PORT", "NODE_ENV", "DEBUG", "LOG_LEVEL", "APP_ENV", "ENVIRONMENT", "TZ",
])
def test_is_required_false_known_optional(var: str):
    assert is_required(var) is False


# ---------------------------------------------------------------------------
# Template file scanning (.env.example etc.)
# ---------------------------------------------------------------------------

def test_scan_env_example(tmp_path: Path):
    (tmp_path / ".env.example").write_text(textwrap.dedent("""\
        # Database
        DATABASE_URL=postgres://localhost/mydb
        SECRET_KEY=changeme

        # Optional
        DEBUG=false
        PORT=3000
    """))
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found
    assert "SECRET_KEY" in found
    assert "DEBUG" in found
    # PORT is always discarded
    assert "PORT" not in found


def test_scan_env_sample_ignores_comments(tmp_path: Path):
    (tmp_path / ".env.sample").write_text("# just a comment\nMY_TOKEN=abc\n")
    found = scan_env_vars(tmp_path)
    assert "MY_TOKEN" in found


# ---------------------------------------------------------------------------
# README section scanning
# ---------------------------------------------------------------------------

def test_readme_env_section_backtick_vars(tmp_path: Path):
    (tmp_path / "README.md").write_text(textwrap.dedent("""\
        # My App

        ## Environment Variables

        Set `DATABASE_URL` to your Postgres connection string.
        Set `REDIS_URL` for caching.

        ## Other Section

        Nothing here.
    """))
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found
    assert "REDIS_URL" in found


def test_readme_env_section_export_lines(tmp_path: Path):
    (tmp_path / "README.md").write_text(textwrap.dedent("""\
        ## Setup

        ```bash
        export API_KEY=your_key_here
        export APP_SECRET=abc123
        ```
    """))
    found = scan_env_vars(tmp_path)
    assert "API_KEY" in found
    assert "APP_SECRET" in found


def test_readme_ignores_non_env_sections(tmp_path: Path):
    (tmp_path / "README.md").write_text(textwrap.dedent("""\
        ## Usage

        Run `SOME_INTERNAL_VAR=1` locally (not an env var doc).
    """))
    # SOME_INTERNAL_VAR appears outside an env section so source scan
    # won't catch it (no source files), and README scan only reads env sections.
    found = scan_env_vars(tmp_path)
    assert "SOME_INTERNAL_VAR" not in found


# ---------------------------------------------------------------------------
# Source file scanning — language pattern tests
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return p


def test_scan_js_process_env(tmp_path: Path):
    _write(tmp_path, "app.js", "const key = process.env.STRIPE_KEY;\n")
    found = scan_env_vars(tmp_path)
    assert "STRIPE_KEY" in found


def test_scan_ts_process_env_bracket(tmp_path: Path):
    _write(tmp_path, "config.ts", "const x = process.env['DATABASE_URL'];\n")
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found


def test_scan_python_os_environ(tmp_path: Path):
    _write(tmp_path, "settings.py", "DB = os.environ['DATABASE_URL']\n")
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found


def test_scan_python_os_getenv(tmp_path: Path):
    _write(tmp_path, "settings.py", "secret = os.getenv('APP_SECRET')\n")
    found = scan_env_vars(tmp_path)
    assert "APP_SECRET" in found


def test_scan_ruby_env(tmp_path: Path):
    _write(tmp_path, "app.rb", "token = ENV['API_TOKEN']\n")
    found = scan_env_vars(tmp_path)
    assert "API_TOKEN" in found


def test_scan_go_getenv(tmp_path: Path):
    _write(tmp_path, "main.go", 'dsn := os.Getenv("DATABASE_URL")\n')
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found


def test_scan_java_system_getenv(tmp_path: Path):
    _write(tmp_path, "App.java", 'String key = System.getenv("API_KEY");\n')
    found = scan_env_vars(tmp_path)
    assert "API_KEY" in found


def test_scan_kotlin(tmp_path: Path):
    _write(tmp_path, "App.kt", 'val secret = System.getenv("JWT_SECRET")\n')
    found = scan_env_vars(tmp_path)
    assert "JWT_SECRET" in found


def test_scan_csharp(tmp_path: Path):
    _write(tmp_path, "Config.cs", 'var url = Environment.GetEnvironmentVariable("DATABASE_URL");\n')
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found


def test_scan_rust(tmp_path: Path):
    _write(tmp_path, "main.rs", 'let key = env::var("SECRET_KEY").unwrap();\n')
    found = scan_env_vars(tmp_path)
    assert "SECRET_KEY" in found


def test_scan_php_getenv(tmp_path: Path):
    _write(tmp_path, "config.php", '$db = getenv("DATABASE_URL");\n')
    found = scan_env_vars(tmp_path)
    assert "DATABASE_URL" in found


def test_scan_unknown_extension_skipped(tmp_path: Path):
    # .xyz files have no patterns — should not be scanned
    _write(tmp_path, "data.xyz", "process.env.SHOULD_NOT_FIND=1\n")
    found = scan_env_vars(tmp_path)
    assert "SHOULD_NOT_FIND" not in found


# ---------------------------------------------------------------------------
# Skip rules
# ---------------------------------------------------------------------------

def test_scan_skips_node_modules(tmp_path: Path):
    nm = tmp_path / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("process.env.NODE_MODULES_VAR\n")
    found = scan_env_vars(tmp_path)
    assert "NODE_MODULES_VAR" not in found


def test_scan_skips_large_files(tmp_path: Path):
    big = tmp_path / "big.js"
    # 257 KB of content
    big.write_text("process.env.BIG_VAR\n" * (257 * 1024 // 20))
    found = scan_env_vars(tmp_path)
    assert "BIG_VAR" not in found


def test_port_always_discarded(tmp_path: Path):
    (tmp_path / ".env.example").write_text("PORT=3000\nSECRET_KEY=abc\n")
    found = scan_env_vars(tmp_path)
    assert "PORT" not in found
    assert "SECRET_KEY" in found
