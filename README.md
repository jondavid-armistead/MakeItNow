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
[makeitnow] Building Docker image my-app:a1b2c3d …
[makeitnow] Running container on port 8080 …

[makeitnow] ✓ Running at http://localhost:8080
```

## How It Works

1. **Clone** — shallow-clones the repo into a temp directory
2. **Detect** — looks for `docker-compose.yml` / `Dockerfile`
3. **Build** — runs `docker build` (skipped when using Compose)
4. **Port** — scans for the next free TCP port from `--port-start`
5. **Run** — starts via `docker compose up -d` (if Compose file found) or `docker run -d`

## Options

| Flag | Default | Description |
|---|---|---|
| `--port-start PORT` | `8080` | First port to try |
| `--container-port PORT` | `80` | Container port to map (docker run path only) |
| `--keep` | off | Keep cloned repo after running |
| `--clone-dir DIR` | temp dir | Clone into a specific directory |

