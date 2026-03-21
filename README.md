# MakeItNow

Clone a GitHub repo, build its Docker image, and run it on an available local port — with one command.

## Requirements

- Python ≥ 3.10
- Docker (with `docker compose` plugin or `docker-compose`)
- Git

## Installation

```bash
python install.py
```

You can also use the thin wrappers:

```bash
sh install.sh
```

On Windows PowerShell:

```powershell
.\install.ps1
```

The installer checks for `docker`, Docker Compose support, and `git`, shows the packages/apps it plans to install for each missing dependency, lets the user choose dependency-by-dependency, creates a local `.makeitnow-venv`, installs MakeItNow into it, and leaves you with a repo-local launcher so you do not have to activate a virtual environment manually.

At the end, it prints a summary of dependency status, the install actions completed during that run, and a short usage tutorial.

## Uninstall

```bash
python uninstall.py
```

You can also use the wrappers:

```bash
sh uninstall.sh
```

On Windows PowerShell:

```powershell
.\uninstall.ps1
```

Uninstall removes only these MakeItNow-managed local artifacts:

- `.makeitnow-venv`
- `install.py`
- `run_makeitnow.py`

It does **not** uninstall Docker, Docker Compose, Git, Python, or any system packages/applications.

If you want to reinstall after uninstall removed `install.py`, use `sh install.sh` on POSIX systems or `.\install.ps1` on Windows PowerShell.

## Usage

```bash
python run_makeitnow.py <github-repo-url> [options]
```

To stop MakeItNow-managed containers, remove their images when possible, and clean leftover `makeitnow_*` temp directories:

```bash
python run_makeitnow.py stop
```

### Examples

```bash
# Clone, build, and run on the next free port starting at 8080
python run_makeitnow.py https://github.com/org/my-app

# Start scanning from port 3000
python run_makeitnow.py https://github.com/org/my-app --port-start 3000

# Keep the cloned repo after running
python run_makeitnow.py https://github.com/org/my-app --keep

# Clone into a specific directory
python run_makeitnow.py https://github.com/org/my-app --clone-dir ./my-app

# Override the container-side port (for docker run path)
python run_makeitnow.py https://github.com/org/my-app --container-port 8080
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

### Multi-service Compose repos

When a repo includes a Compose file with multiple services, MakeItNow keeps Compose as the source of truth for build/startup, inspects every externally published service port, and prints every reachable local URL it finds.

If one service fails to start but others are still running, MakeItNow now reports the running services and their reachable ports anyway, plus a warning about the failed services.

For proxy-style setups such as nginx fronting an app service, MakeItNow validates the published ports against the Compose configuration instead of collapsing everything into one guessed endpoint.

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

## Troubleshooting

If MakeItNow reports that Docker cannot access `/var/run/docker.sock`, that usually means Docker is installed but your user cannot talk to the Docker daemon yet. Common fixes are:

- Start Docker Desktop or the Docker service.
- Add your user to the `docker` group on Linux, then sign out and back in.
- Rerun `python install.py` if Docker, Compose, or Git still need to be installed.

The installer never stores sudo or administrator passwords. If elevated access is needed, the operating system or package manager prompts for it directly.
