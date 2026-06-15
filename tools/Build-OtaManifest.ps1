param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("controller", "sensors")]
    [string]$Device,

    [Parameter(Mandatory = $true)]
    [int]$Version,

    [Parameter(Mandatory = $true)]
    [string]$RawBaseUrl,

    [string[]]$Files = @("main.py", "ota_updater.py")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$key = $env:GREENHOUSE_OTA_HMAC_KEY
if (-not $key) {
    throw "Set GREENHOUSE_OTA_HMAC_KEY before building a manifest."
}

$deviceDir = Join-Path (Get-Location) $Device
if (-not (Test-Path $deviceDir)) {
    throw "Device directory not found: $deviceDir"
}

$base = $RawBaseUrl.TrimEnd("/")
$entries = @()
$payloadLines = New-Object System.Collections.Generic.List[string]
$payloadLines.Add([string]$Version)
$payloadLines.Add($Device)

foreach ($file in $Files) {
    if ($file -match '(^/|\\|:|\.\.)') {
        throw "Unsafe OTA path: $file"
    }

    $localPath = Join-Path $deviceDir $file
    if (-not (Test-Path $localPath)) {
        throw "File not found: $localPath"
    }

    $sha = (Get-FileHash -Path $localPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $url = "$base/$file"
    $entries += [ordered]@{
        path = $file
        url = $url
        sha256 = $sha
    }
    $payloadLines.Add("$file|$sha|$url")
}

$payload = $payloadLines -join "`n"
$hmac = [System.Security.Cryptography.HMACSHA256]::new(
    [System.Text.Encoding]::UTF8.GetBytes($key)
)
$signatureBytes = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload))
$signature = -join ($signatureBytes | ForEach-Object { $_.ToString("x2") })

$manifest = [ordered]@{
    version = $Version
    device = $Device
    files = $entries
    signature = $signature
}

$outputPath = Join-Path $deviceDir "ota_manifest.json"
$json = $manifest | ConvertTo-Json -Depth 5
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine, $utf8NoBom)
Write-Host "Wrote $outputPath" -ForegroundColor Green
Write-Host "Payload signed:" -ForegroundColor DarkGray
Write-Host $payload -ForegroundColor DarkGray
