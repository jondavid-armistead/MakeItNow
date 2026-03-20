# MakeItNow

Clone a GitHub repo, build its Docker image, and run it on an available local port — with one command.

## Requirements

- Python ≥ 3.10
- Docker (with `docker compose` plugin or `docker-compose`)
- Git

## Installation

```bash
pip install -e .
```

## Usage

```bash
makeitnow <github-repo-url> [options]
```

### Examples

```bash
# Clone, build, and run on the next free port starting at 8080
makeitnow https://github.com/org/my-app

# Start scanning from port 3000
makeitnow https://github.com/org/my-app --port-start 3000

# Keep the cloned repo after running
makeitnow https://github.com/org/my-app --keep

# Clone into a specific directory
makeitnow https://github.com/org/my-app --clone-dir ./my-app

# Override the container-side port (for docker run path)
makeitnow https://github.com/org/my-app --container-port 8080
```

### Output

```
[makeitnow] Cloning https://github.com/org/my-app …
[makeitnow] Cloned to /tmp/makeitnow_abc123
[makeitnow] Scanning for environment variables…
[makeitnow] Found 2 environment variable(s) referenced in this repo:
  …
[makeitnow] Building Docker image my-app:a1b2c3d …
[makeitnow] Running container on port 8080 …

[makeitnow] ✓ Running at http://localhost:8080
```

## How It Works

1. **Clone** — shallow-clones the repo into a temp directory
2. **Scan** — discovers environment variables referenced in the repo (see below)
3. **Detect** — looks for `docker-compose.yml` / `Dockerfile`
4. **Build** — runs `docker build` (skipped when using Compose)
5. **Port** — scans for the next free TCP port from `--port-start`
6. **Run** — starts via `docker compose up -d` (if Compose file found) or `docker run -d`

## Environment Variable Discovery

Before building, MakeItNow scans the repo for any environment variables the app expects and interactively creates a `.env` file. Scanning uses three layers, highest confidence first:

1. **Template files** — `.env.example`, `.env.sample`, `.env.template`, `.env.dist` (committed by the developer specifically to document required vars)
2. **README sections** — parses headers matching "Environment Variables", "Configuration", "Setup", etc. and extracts variable names from code blocks, backtick references, and `export VAR=` lines
3. **Source code** — scans files by extension using language-specific patterns:

| Language | Pattern |
|---|---|
| JavaScript / TypeScript | `process.env.VAR` / `process.env['VAR']` |
| Python | `os.environ['VAR']` / `os.getenv('VAR')` |
| Ruby | `ENV['VAR']` / `ENV.fetch('VAR')` |
| Go | `os.Getenv("VAR")` |
| Java / Kotlin | `System.getenv("VAR")` |
| C# / .NET | `Environment.GetEnvironmentVariable("VAR")` |
| Rust | `env::var("VAR")` |
| PHP | `getenv('VAR')` / `$_ENV['VAR']` |

Files in `node_modules`, lock files, minified bundles, and files over 256 KB are skipped to keep scanning fast.

### Interactive prompt

Once discovered, MakeItNow lists the variables and asks for confirmation before writing anything. Variables that look like secrets, credentials, or connection strings (names containing `SECRET`, `TOKEN`, `PASSWORD`, `_KEY`, `_URL`, `_DSN`, etc.) are flagged as **required** and prompted individually — similar to how `git` prompts for credentials:

```
[makeitnow] Found 4 environment variable(s) referenced in this repo:

  DATABASE_URL=  (required)
  STRIPE_SECRET_KEY=  (required)
  NODE_ENV=
  LOG_LEVEL=

[makeitnow] Create .env with these variables? [Y/n]: y

[makeitnow] Enter values for required variables (press Enter to skip):
  DATABASE_URL: postgres://localhost/myapp
  STRIPE_SECRET_KEY:
  ⚠  STRIPE_SECRET_KEY left blank — the container may not function correctly without it.

[makeitnow] Created .env (4 variable(s)):
────────────────────────────────────────
  DATABASE_URL=postgres://localhost/myapp
  STRIPE_SECRET_KEY=
  NODE_ENV=
  LOG_LEVEL=
────────────────────────────────────────
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--port-start PORT` | `8080` | First port to try |
| `--container-port PORT` | `80` | Container port to map (docker run path only) |
| `--keep` | off | Keep cloned repo after running |
| `--clone-dir DIR` | temp dir | Clone into a specific directory |

