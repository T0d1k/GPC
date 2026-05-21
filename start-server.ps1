$bundledPython = "C:\Users\surface\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$serverScript = Join-Path $PSScriptRoot "server.py"

if (Test-Path $bundledPython) {
  & $bundledPython $serverScript
  exit $LASTEXITCODE
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if ($pythonCommand) {
  & $pythonCommand.Source $serverScript
  exit $LASTEXITCODE
}

Write-Error "Python was not found. Install Python or update start-server.ps1 with the correct path."
exit 1
