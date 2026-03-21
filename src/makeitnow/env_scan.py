"""Scan a repository for environment variable references and build a .env file.

Scanning order (highest to lowest confidence):
1. Committed template files  (.env.example, .env.sample, etc.)
2. README environment sections (headers matching env/config keywords)
3. Source file patterns       (extension-keyed, language-specific regex)
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Language-specific patterns grouped by file extension.
# Each tuple is (compiled_regex, label). Group 1 must be the variable name.
# ---------------------------------------------------------------------------
_js_patterns = [
    re.compile(r"process\.env\.([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r'process\.env\[[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]\]'),
]
_python_patterns = [
    re.compile(r'os\.environ\[[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]\]'),
    re.compile(r'os\.environ\.get\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
    re.compile(r'os\.getenv\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
]
_ruby_patterns = [
    re.compile(r'ENV\[[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]\]'),
    re.compile(r'ENV\.fetch\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
]
_go_patterns = [
    re.compile(r'os\.Getenv\(["\'`]([A-Za-z_][A-Za-z0-9_]*)'),
]
_java_kotlin_patterns = [
    re.compile(r'System\.getenv\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
]
_csharp_patterns = [
    re.compile(r'Environment\.GetEnvironmentVariable\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
]
_rust_patterns = [
    re.compile(r'env::var\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
    re.compile(r'env::var_os\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
]
_php_patterns = [
    re.compile(r'getenv\([\'"]([A-Za-z_][A-Za-z0-9_]*)'),
    re.compile(r'\$_ENV\[[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]\]'),
    re.compile(r'\$_SERVER\[[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]\]'),
]

# Extension → list of patterns (only these patterns run for that file type)
_EXT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    ".js":   _js_patterns,
    ".jsx":  _js_patterns,
    ".mjs":  _js_patterns,
    ".cjs":  _js_patterns,
    ".ts":   _js_patterns,
    ".tsx":  _js_patterns,
    ".py":   _python_patterns,
    ".rb":   _ruby_patterns,
    ".go":   _go_patterns,
    ".java": _java_kotlin_patterns,
    ".kt":   _java_kotlin_patterns,
    ".kts":  _java_kotlin_patterns,
    ".cs":   _csharp_patterns,
    ".rs":   _rust_patterns,
    ".php":  _php_patterns,
}

# ---------------------------------------------------------------------------
# README section scanning
# ---------------------------------------------------------------------------
_ENV_HEADER_RE = re.compile(
    r"(?:environment\s*variables?|env\s*vars?|configuration|setup|getting\s*started|prerequisites)",
    re.IGNORECASE,
)
_README_VAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"`([A-Z_][A-Z0-9_]{2,})`"),                        # `VAR_NAME`
    re.compile(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]{2,})=", re.MULTILINE),  # VAR= / export VAR=
    re.compile(r"\*\*([A-Z_][A-Z0-9_]{2,})\*\*"),                  # **VAR_NAME**
]

# ---------------------------------------------------------------------------
# File / directory skip rules
# ---------------------------------------------------------------------------
_ENV_TEMPLATE_NAMES = (".env.example", ".env.sample", ".env.template", ".env.dist")

_SKIP_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".tox", "vendor", "dist", "build", ".next", ".nuxt",
    "coverage", ".pytest_cache", "target", ".gradle",
    "bower_components", ".yarn", ".pnp",
})

_SKIP_FILENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "Gemfile.lock", "poetry.lock", "Pipfile.lock", "composer.lock",
    "Cargo.lock", "go.sum", "packages.lock.json", "paket.lock",
    "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt",
    "LICENSE", "LICENSE.md", "LICENSE.txt",
})

_MAX_FILE_BYTES = 256 * 1024  # 256 KB

# ---------------------------------------------------------------------------
# Required-variable heuristics
# ---------------------------------------------------------------------------
_REQUIRED_SUBSTRINGS = (
    "SECRET", "TOKEN", "PASSWORD", "PASSWD", "PRIVATE",
    "CREDENTIAL", "WEBHOOK", "ENCRYPT",
)
_REQUIRED_SUFFIXES = (
    "_KEY", "_URL", "_DSN", "_URI", "_HOST",
    "_USER", "_PASS", "_CERT", "_PEM",
)
_OPTIONAL_VARS = frozenset({
    "PORT", "NODE_ENV", "APP_ENV", "RAILS_ENV", "DEBUG",
    "LOG_LEVEL", "ENVIRONMENT", "TZ", "LANG", "HOME", "PATH",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_required(var: str) -> bool:
    """Return True if *var* likely needs a real value (API key, URL, secret, etc.)."""
    if var in _OPTIONAL_VARS:
        return False
    u = var.upper()
    return (
        any(s in u for s in _REQUIRED_SUBSTRINGS)
        or any(u.endswith(s) for s in _REQUIRED_SUFFIXES)
    )


def scan_env_vars(repo_dir: Path) -> set[str]:
    """Scan *repo_dir* for env var references and return the set of variable names.

    Scanning order (highest confidence first):
    1. Committed template files (.env.example etc.)
    2. README environment variable sections
    3. Extension-keyed source file patterns

    ``PORT`` is always discarded — MakeItNow manages it.
    """
    found: set[str] = set()

    _scan_template_files(repo_dir, found)
    _scan_readmes(repo_dir, found)
    _scan_source_files(repo_dir, found)

    found.discard("PORT")
    return found


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_template_files(repo_dir: Path, found: set[str]) -> None:
    for name in _ENV_TEMPLATE_NAMES:
        template = repo_dir / name
        if not template.is_file():
            continue
        for line in template.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            var = line.split("=", 1)[0].strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", var):
                found.add(var)


def _scan_readmes(repo_dir: Path, found: set[str]) -> None:
    readme_candidates = (
        "README.md", "README.rst", "README.txt", "README",
        "readme.md", "readme.rst", "readme.txt",
        "CONTRIBUTING.md", "CONTRIBUTING.rst",
        "docs/configuration.md", "docs/env.md",
    )
    for name in readme_candidates:
        path = repo_dir / name
        if path.is_file():
            _extract_readme_env_section(path, found)


def _extract_readme_env_section(path: Path, found: set[str]) -> None:
    """Parse a README and extract variable names from env-related header sections."""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return

    header_re = re.compile(r"^(#{1,4})\s+(.+)")
    in_env_section = False
    current_level = 0

    for line in lines:
        m = header_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if _ENV_HEADER_RE.search(title):
                in_env_section = True
                current_level = level
            elif in_env_section and level <= current_level:
                in_env_section = False
            continue

        if not in_env_section:
            continue

        for pattern in _README_VAR_PATTERNS:
            for match in pattern.finditer(line):
                candidate = match.group(1)
                if re.match(r"^[A-Z_][A-Z0-9_]{2,}$", candidate):
                    found.add(candidate)


def _should_skip(path: Path, root: Path) -> bool:
    """Return True if *path* should be excluded from source scanning."""
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    if any(part in _SKIP_DIRS for part in rel_parts):
        return True
    if path.name in _SKIP_FILENAMES:
        return True
    # README/docs already handled by _scan_readmes
    if path.name.lower().startswith("readme") or path.name.lower().startswith("contributing"):
        return True
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return True
    except OSError:
        return True
    return False


def _scan_source_files(root: Path, found: set[str]) -> None:
    """Scan only files with a recognized extension using matching patterns."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        patterns = _EXT_PATTERNS.get(path.suffix.lower())
        if not patterns:
            continue  # Unknown extension — skip entirely
        if _should_skip(path, root):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for pattern in patterns:
            for m in pattern.finditer(text):
                found.add(m.group(1))
