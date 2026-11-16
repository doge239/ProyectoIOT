param(
    [string]$BackendUrl = 'https://proyectoiot-production-c42015b2.up.railway.app',
    [int]$VersionCode = 3,
    [string]$VersionName = '1.2'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:ANDROID_HOME) {
    $sdkDirectory = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path -LiteralPath $sdkDirectory) { $env:ANDROID_HOME = $sdkDirectory }
}
if (-not $env:ANDROID_HOME -or -not (Test-Path -LiteralPath $env:ANDROID_HOME)) {
    throw 'Instala Android SDK y configura ANDROID_HOME antes de compilar.'
}
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Falló npm ci.' }
    }
    & node scripts/mobile-config.mjs $BackendUrl
    if ($LASTEXITCODE -ne 0) { throw 'La URL del backend no es válida.' }
    if (-not (Test-Path -LiteralPath 'android')) {
        & npx cap add android
        if ($LASTEXITCODE -ne 0) { throw 'Falló la creación del proyecto Android.' }
    }
    & npm run mobile:sync
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación o sincronización Angular.' }
    & node scripts/android-version.mjs $VersionCode $VersionName
    if ($LASTEXITCODE -ne 0) { throw 'Falló la configuración de versión Android.' }
    Push-Location 'android'
    try {
        & .\gradlew.bat assembleDebug --console=plain
        if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación Android.' }
    } finally { Pop-Location }
    $outputDirectory = Join-Path $PSScriptRoot 'apk'
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $apkPath = Join-Path $outputDirectory "Parquea-Admin-$VersionName-debug.apk"
    Copy-Item -LiteralPath 'android\app\build\outputs\apk\debug\app-debug.apk' -Destination $apkPath -Force
    Write-Host "APK de prueba generado: $apkPath"
} finally { Pop-Location }
