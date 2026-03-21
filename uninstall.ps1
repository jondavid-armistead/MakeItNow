$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$repoRoot/src;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = "$repoRoot/src"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m makeitnow.uninstaller @args
} else {
    python -m makeitnow.uninstaller @args
}
