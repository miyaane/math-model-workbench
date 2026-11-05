param([string]$Python = 'python')

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$environment = Join-Path $projectRoot '.venv'
$environmentPython = Join-Path $environment 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $environmentPython -PathType Leaf)) {
    & $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or later is required. Pass its executable with -Python.' }
    & $Python -m venv $environment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project environment.' }
}

& $environmentPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install the workbench dependencies.' }

& $environmentPython -X utf8 -m unittest discover -s (Join-Path $projectRoot 'tools') -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Workbench tests failed.' }

New-Item -ItemType Directory -Path (Join-Path $projectRoot 'cases') -Force | Out-Null
$workspaceFile = Join-Path $projectRoot 'workspace.json'
if (-not (Test-Path -LiteralPath $workspaceFile)) {
    '{"schema_version":1,"active_case":".","stage":"awaiting_new_problem"}' | Set-Content -LiteralPath $workspaceFile -Encoding utf8
}
if (-not (Get-Command xelatex -ErrorAction SilentlyContinue)) {
    Write-Output 'XeLaTeX is required for paper compilation. Install TeX Live and add it to PATH.'
}
Write-Output 'Workbench setup complete. Provide a new problem folder to create a case.'
