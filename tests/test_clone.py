"""Tests for clone helpers (no network calls)."""

from makeitnow.clone import repo_name_from_url


def test_repo_name_from_https_url():
    assert repo_name_from_url("https://github.com/org/my-repo") == "my-repo"


def test_repo_name_strips_git_suffix():
    assert repo_name_from_url("https://github.com/org/my-repo.git") == "my-repo"


def test_repo_name_trailing_slash():
    assert repo_name_from_url("https://github.com/org/my-repo/") == "my-repo"


def test_repo_name_lowercased():
    assert repo_name_from_url("https://github.com/Org/MyRepo") == "myrepo"
