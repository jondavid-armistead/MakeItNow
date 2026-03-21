$ErrorActionPreference = "Stop"

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 "$PSScriptRoot/install.py" @args
} else {
    python "$PSScriptRoot/install.py" @args
}
