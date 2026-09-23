$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
if (-not $env:PYTHON_BIN) { $env:PYTHON_BIN = "python" }
& $env:PYTHON_BIN "$Root\run.py" @args
exit $LASTEXITCODE
