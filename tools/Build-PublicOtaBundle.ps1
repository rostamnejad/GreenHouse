param(
    [int]$Version = 2,
    [string]$Owner = "rostamnejad",
    [string]$Repository = "GreenHouse-OTA",
    [string]$Branch = "main",
    [string]$OutputDir = "ota_public"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$key = $env:GREENHOUSE_OTA_HMAC_KEY
if (-not $key) {
    throw "Set GREENHOUSE_OTA_HMAC_KEY before building the public OTA bundle."
}

$root = Get-Location
$outputRoot = Join-Path $root $OutputDir
$filesByDevice = @{
    controller = @(
        "version.py",
        "main.py",
        "ota_updater.py",
        "telegram_notifier.py",
        "ssd1306.py",
        "oled_display.py"
    )
    sensors = @("version.py", "main.py", "ota_updater.py")
}

if (Test-Path $outputRoot) {
    Remove-Item -LiteralPath $outputRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

foreach ($device in @("controller", "sensors")) {
    $deviceOut = Join-Path $outputRoot $device
    New-Item -ItemType Directory -Force -Path $deviceOut | Out-Null
    $files = $filesByDevice[$device]

    foreach ($file in $files) {
        Copy-Item -LiteralPath (Join-Path $root "$device\$file") -Destination (Join-Path $deviceOut $file)
    }

    $rawBaseUrl = "https://raw.githubusercontent.com/$Owner/$Repository/$Branch/$device"
    $env:GREENHOUSE_OTA_HMAC_KEY = $key
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools\Build-OtaManifest.ps1") `
        -Device $device `
        -Version $Version `
        -RawBaseUrl $rawBaseUrl `
        -Files $files | Out-Null

    Move-Item -LiteralPath (Join-Path $root "$device\ota_manifest.json") -Destination (Join-Path $deviceOut "ota_manifest.json") -Force
}

Write-Host "Public OTA bundle written to $outputRoot" -ForegroundColor Green
Write-Host "Publish this folder to https://github.com/$Owner/$Repository on branch $Branch." -ForegroundColor DarkGray
