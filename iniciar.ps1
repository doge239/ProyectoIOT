param([switch]$NoBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExecutable = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Falta el entorno Python. Sigue los pasos de instalación en README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'backend\.env'))) {
    & $pythonExecutable -m backend.configure
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la configuración local.' }
}
if (-not $NoBuild) {
    Push-Location (Join-Path $PSScriptRoot 'frontend')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            & npm ci
            if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Angular.' }
        }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación Angular.' }
    } finally { Pop-Location }
}
Write-Host 'Panel: http://127.0.0.1:8080 | Credenciales: .local/credenciales.txt'
& $pythonExecutable servidor.py
exit $LASTEXITCODE
