"""Tests for CLI entrypoint wiring."""

from makeitnow.cli import main


def test_cli_exports_main():
    assert callable(main)
