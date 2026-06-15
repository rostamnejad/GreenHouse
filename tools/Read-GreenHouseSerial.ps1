param(
    [string]$Port,
    [int]$BaudRate = 115200,
    [switch]$ShowRaw,
    [switch]$Sample
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TEMP_MIN_C = 18.0
$TEMP_MAX_C = 28.0
$HUMIDITY_MIN_PERCENT = 45.0
$HUMIDITY_MAX_PERCENT = 70.0

function Resolve-SerialPort {
    param([string]$RequestedPort)

    if ($RequestedPort) {
        return $RequestedPort
    }

    $cimPorts = @(Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue)
    $usbPorts = @(
        $cimPorts |
            Where-Object { $_.Description -match "USB|Serial|UART|CP210|CH340|ESP|Silicon" } |
            Sort-Object DeviceID
    )

    if ($usbPorts.Count -gt 0) {
        return $usbPorts[0].DeviceID
    }

    $portNames = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
    if ($portNames.Count -eq 1) {
        return $portNames[0]
    }

    if ($portNames.Count -gt 1) {
        throw "Multiple serial ports found: $($portNames -join ', '). Use -Port COMx."
    }

    throw "No serial ports found. Connect the controller board and try again."
}

function Parse-ParameterLine {
    param([string]$Line)

    $text = $Line.Trim()
    if ($text.StartsWith("PARAMETERS ")) {
        $text = $text.Substring("PARAMETERS ".Length).Trim()
    }

    if ($text -match "^HUMIDITY\s+([0-9.]+)\s+->\s+([A-Za-z_]+)") {
        return @{
            "HUMIDITY" = $Matches[1]
            "STATE" = $Matches[2]
            "LEGACY" = "true"
        }
    }

    if ($text -notmatch "TEMP_C=|HUMIDITY=|PRESSURE_MBAR=") {
        return $null
    }

    $values = @{}
    foreach ($token in ($text -split "\s+")) {
        $pair = $token -split "=", 2
        if ($pair.Count -eq 2 -and $pair[0]) {
            $values[$pair[0].ToUpperInvariant()] = $pair[1]
        }
    }

    if ($values.Count -eq 0) {
        return $null
    }

    return $values
}

function Get-Field {
    param(
        [hashtable]$Data,
        [string]$Key,
        [string]$Default = "--"
    )

    if ($Data.ContainsKey($Key) -and $Data[$Key]) {
        return [string]$Data[$Key]
    }

    return $Default
}

function Get-Number {
    param(
        [hashtable]$Data,
        [string]$Key
    )

    if (-not $Data.ContainsKey($Key) -or -not $Data[$Key]) {
        return $null
    }

    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    try {
        return [double]::Parse([string]$Data[$Key], $culture)
    } catch {
        return $null
    }
}

function Format-Number {
    param(
        [object]$Value,
        [string]$Format = "0.00"
    )

    if ($null -eq $Value) {
        return "--"
    }

    return $Value.ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-Bar {
    param(
        [object]$Percent,
        [int]$Width = 24
    )

    if ($null -eq $Percent) {
        return "[" + ("." * $Width) + "]"
    }

    $clamped = [Math]::Max(0, [Math]::Min(100, [double]$Percent))
    $filled = [int][Math]::Round(($clamped / 100) * $Width)
    return "[" + ("#" * $filled) + ("." * ($Width - $filled)) + "]"
}

function Format-SignedGap {
    param(
        [double]$Value,
        [string]$Unit
    )

    return ("{0:0.00} {1}" -f [Math]::Abs($Value), $Unit)
}

function Get-RangeAnalysis {
    param(
        [object]$Value,
        [double]$Min,
        [double]$Max,
        [string]$Unit,
        [string]$LowAction,
        [string]$HighAction
    )

    $range = $Max - $Min
    if ($null -eq $Value) {
        return @{
            Status = "WAITING"
            Color = "DarkGray"
            Action = "waiting for reading"
            Detail = ("standard {0:0.#}-{1:0.#} {2}" -f $Min, $Max, $Unit)
            Gap = 0.0
            Priority = 0.0
        }
    }

    $number = [double]$Value
    if ($number -lt $Min) {
        $gap = $Min - $number
        return @{
            Status = "LOW"
            Color = "Yellow"
            Action = $LowAction
            Detail = ("below min by {0}; standard {1:0.#}-{2:0.#} {3}" -f (Format-SignedGap $gap $Unit), $Min, $Max, $Unit)
            Gap = $gap
            Priority = $gap / $range
        }
    }

    if ($number -gt $Max) {
        $gap = $number - $Max
        return @{
            Status = "HIGH"
            Color = "Red"
            Action = $HighAction
            Detail = ("above max by {0}; standard {1:0.#}-{2:0.#} {3}" -f (Format-SignedGap $gap $Unit), $Min, $Max, $Unit)
            Gap = $gap
            Priority = $gap / $range
        }
    }

    $position = (($number - $Min) / $range) * 100
    if ($position -lt 33) {
        $zone = "lower healthy zone"
    } elseif ($position -gt 67) {
        $zone = "upper healthy zone"
    } else {
        $zone = "middle healthy zone"
    }

    return @{
        Status = "OK"
        Color = "Green"
        Action = "no control needed"
        Detail = ("inside range at {0:0}% ({1}); standard {2:0.#}-{3:0.#} {4}" -f $position, $zone, $Min, $Max, $Unit)
        Gap = 0.0
        Priority = 0.0
    }
}

function Get-StateInfo {
    param([string]$State)

    switch ($State.ToLowerInvariant()) {
        "alert" { return @{ Text = "ALERT"; Color = "Red"; Hint = "climate needs attention" } }
        "warning" { return @{ Text = "WARNING"; Color = "Yellow"; Hint = "check temp or humidity" } }
        "critical_dry" { return @{ Text = "CRITICAL DRY"; Color = "Red"; Hint = "humidity is critically low" } }
        "dry" { return @{ Text = "DRY"; Color = "Red"; Hint = "humidity is low" } }
        "low" { return @{ Text = "LOW"; Color = "Yellow"; Hint = "watch humidity" } }
        "low_humidity" { return @{ Text = "LOW"; Color = "Yellow"; Hint = "watch humidity" } }
        "good" { return @{ Text = "GOOD"; Color = "Green"; Hint = "healthy range" } }
        "humidity_good" { return @{ Text = "GOOD"; Color = "Green"; Hint = "humidity is healthy" } }
        "humid" { return @{ Text = "HUMID"; Color = "Cyan"; Hint = "humidity is high" } }
        "too_humid" { return @{ Text = "TOO HUMID"; Color = "Magenta"; Hint = "reduce humidity" } }
        "too_cold" { return @{ Text = "TOO COLD"; Color = "Blue"; Hint = "temperature is very low" } }
        "cold" { return @{ Text = "COLD"; Color = "Cyan"; Hint = "temperature is low" } }
        "temp_good" { return @{ Text = "GOOD"; Color = "Green"; Hint = "temperature is healthy" } }
        "warm" { return @{ Text = "WARM"; Color = "Yellow"; Hint = "temperature is high" } }
        "hot" { return @{ Text = "HOT"; Color = "Red"; Hint = "temperature is very high" } }
        "waiting" { return @{ Text = "WAITING"; Color = "DarkGray"; Hint = "no reading yet" } }
        default { return @{ Text = $State.ToUpperInvariant(); Color = "White"; Hint = "latest state" } }
    }
}

function Get-TemperatureInfo {
    param([object]$Temperature)

    if ($null -eq $Temperature) {
        return @{ Color = "DarkGray"; Hint = "waiting" }
    }

    if ($Temperature -lt 18) {
        return @{ Color = "Cyan"; Hint = "cool" }
    }

    if ($Temperature -le 28) {
        return @{ Color = "Green"; Hint = "comfortable" }
    }

    return @{ Color = "Yellow"; Hint = "warm" }
}

function Get-PressureInfo {
    param([object]$Pressure)

    if ($null -eq $Pressure) {
        return @{ Color = "DarkGray"; Hint = "waiting" }
    }

    if ($Pressure -lt 1000) {
        return @{ Color = "Yellow"; Hint = "low" }
    }

    if ($Pressure -le 1025) {
        return @{ Color = "Green"; Hint = "normal" }
    }

    return @{ Color = "Cyan"; Hint = "high" }
}

function Write-Metric {
    param(
        [string]$Label,
        [string]$Value,
        [string]$Unit,
        [string]$Hint,
        [string]$Color = "White",
        [string]$Bar = ""
    )

    Write-Host ("  {0,-15} " -f $Label) -NoNewline -ForegroundColor DarkGray
    Write-Host ("{0,10} {1,-6}" -f $Value, $Unit) -NoNewline -ForegroundColor $Color
    if ($Bar) {
        Write-Host (" {0}" -f $Bar) -NoNewline -ForegroundColor $Color
    }
    if ($Hint) {
        Write-Host ("  {0}" -f $Hint) -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
}

function Write-ControlLine {
    param(
        [string]$Label,
        [hashtable]$Analysis
    )

    Write-Host ("  {0,-15} " -f $Label) -NoNewline -ForegroundColor DarkGray
    Write-Host ("{0,-8}" -f $Analysis.Status) -NoNewline -ForegroundColor $Analysis.Color
    Write-Host (" {0}" -f $Analysis.Detail) -NoNewline -ForegroundColor DarkGray
    Write-Host (" | {0}" -f $Analysis.Action) -ForegroundColor $Analysis.Color
}

function Write-ControlDecision {
    param(
        [hashtable]$TempAnalysis,
        [hashtable]$HumidityAnalysis
    )

    Write-Host ""
    Write-Host "Control decision" -ForegroundColor Green

    $tempNeedsControl = $TempAnalysis.Status -ne "OK" -and $TempAnalysis.Status -ne "WAITING"
    $humidityNeedsControl = $HumidityAnalysis.Status -ne "OK" -and $HumidityAnalysis.Status -ne "WAITING"

    if (-not $tempNeedsControl -and -not $humidityNeedsControl) {
        Write-Host "  Target          " -NoNewline -ForegroundColor DarkGray
        Write-Host "NONE" -NoNewline -ForegroundColor Green
        Write-Host "     temperature and humidity are both inside the standard range" -ForegroundColor DarkGray
    } elseif ($tempNeedsControl -and $humidityNeedsControl) {
        $priority = "temperature"
        if ($HumidityAnalysis.Priority -ge $TempAnalysis.Priority) {
            $priority = "humidity"
        }

        Write-Host "  Target          " -NoNewline -ForegroundColor DarkGray
        Write-Host "BOTH" -NoNewline -ForegroundColor Yellow
        Write-Host ("     priority: {0}" -f $priority) -ForegroundColor Yellow
    } elseif ($humidityNeedsControl) {
        Write-Host "  Target          " -NoNewline -ForegroundColor DarkGray
        Write-Host "HUMIDITY" -NoNewline -ForegroundColor $HumidityAnalysis.Color
        Write-Host (" | {0}" -f $HumidityAnalysis.Action) -ForegroundColor $HumidityAnalysis.Color
    } else {
        Write-Host "  Target          " -NoNewline -ForegroundColor DarkGray
        Write-Host "TEMPERATURE" -NoNewline -ForegroundColor $TempAnalysis.Color
        Write-Host (" | {0}" -f $TempAnalysis.Action) -ForegroundColor $TempAnalysis.Color
    }

    Write-ControlLine "Temperature" $TempAnalysis
    Write-ControlLine "Humidity" $HumidityAnalysis
}

function Show-Dashboard {
    param(
        [hashtable]$Data,
        [string]$SerialPort,
        [int]$SerialBaud,
        [datetime]$StartedAt,
        [object]$LastParameterAt,
        [string]$LastLine
    )

    $temp = Get-Number $Data "TEMP_C"
    $humidity = Get-Number $Data "HUMIDITY"
    $pressure = Get-Number $Data "PRESSURE_MBAR"
    $altitude = Get-Number $Data "ALTITUDE_M"
    $state = Get-Field $Data "STATE" "waiting"
    $tempState = Get-Field $Data "TEMP_STATE" ""
    $humidityState = Get-Field $Data "HUMIDITY_STATE" ""
    $stateInfo = Get-StateInfo $state
    if ($tempState) {
        $tempInfo = Get-StateInfo $tempState
    } else {
        $tempInfo = Get-TemperatureInfo $temp
    }
    if ($humidityState) {
        $humidityInfo = Get-StateInfo $humidityState
    } else {
        $humidityInfo = $stateInfo
    }
    $pressureInfo = Get-PressureInfo $pressure
    $tempAnalysis = Get-RangeAnalysis `
        $temp `
        $TEMP_MIN_C `
        $TEMP_MAX_C `
        "C" `
        "heat / raise temperature" `
        "cool / ventilate"
    $humidityAnalysis = Get-RangeAnalysis `
        $humidity `
        $HUMIDITY_MIN_PERCENT `
        $HUMIDITY_MAX_PERCENT `
        "%" `
        "increase humidity" `
        "decrease humidity / ventilate"

    $timeText = Get-Field $Data "TIME"
    $dateText = Get-Field $Data "JDATE"
    $ageText = "waiting"
    if ($null -ne $LastParameterAt) {
        $age = ((Get-Date) - $LastParameterAt).TotalSeconds
        $ageText = ("{0:0}s ago" -f $age)
    }

    Clear-Host
    Write-Host "GreenHouse Controller - Live Serial Dashboard" -ForegroundColor Green
    Write-Host ("Port {0}  |  Baud {1}  |  Updated {2}  |  Running {3:hh\:mm\:ss}" -f `
        $SerialPort, $SerialBaud, $ageText, ((Get-Date) - $StartedAt)) -ForegroundColor DarkGray
    Write-Host ("-" * 78) -ForegroundColor DarkGray
    Write-ControlDecision $tempAnalysis $humidityAnalysis
    Write-Host ("-" * 78) -ForegroundColor DarkGray

    Write-Metric "Temperature" (Format-Number $temp) "C" $tempInfo.Hint $tempInfo.Color
    Write-Metric "Humidity" (Format-Number $humidity) "%" $humidityInfo.Hint $humidityInfo.Color (Get-Bar $humidity)
    Write-Metric "Pressure" (Format-Number $pressure) "mbar" $pressureInfo.Hint $pressureInfo.Color
    Write-Metric "Altitude" (Format-Number $altitude "0.0") "m" "barometric estimate" "White"
    Write-Metric "Local time" $timeText "" "from sensor board" "White"
    Write-Metric "Jalali date" $dateText "" "from sensor board" "White"

    Write-Host ""
    Write-Host "  RGB state       " -NoNewline -ForegroundColor DarkGray
    Write-Host ("{0,-16}" -f $stateInfo.Text) -NoNewline -ForegroundColor $stateInfo.Color
    Write-Host ("  {0}" -f $stateInfo.Hint) -ForegroundColor DarkGray

    Write-Host ("-" * 78) -ForegroundColor DarkGray
    if ($LastLine) {
        Write-Host "Last serial line:" -ForegroundColor DarkGray
        Write-Host ("  " + $LastLine.Trim()) -ForegroundColor DarkGray
    } else {
        Write-Host "Waiting for serial data..." -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Press Ctrl+C to exit." -ForegroundColor DarkGray
}

$resolvedPort = Resolve-SerialPort $Port
$latest = @{}
$startedAt = Get-Date
$lastParameterAt = $null
$lastLine = ""

if ($Sample) {
    $lastLine = "PARAMETERS TIME=21:45 JDATE=1405/03/25 TEMP_C=31.20 HUMIDITY=38.10 PRESSURE_MBAR=863.12 ALTITUDE_M=1332.4 TEMP_STATE=warm HUMIDITY_STATE=low_humidity STATE=warning"
    $latest = Parse-ParameterLine $lastLine
    $lastParameterAt = Get-Date
    Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine
    return
}

$serial = [System.IO.Ports.SerialPort]::new($resolvedPort, $BaudRate, "None", 8, "One")
$serial.ReadTimeout = 1000
$serial.NewLine = "`n"

try {
    try {
        $serial.Open()
    } catch {
        Write-Host "Could not open $resolvedPort." -ForegroundColor Red
        Write-Host "Close Thonny, Arduino Serial Monitor, mpremote, or any other app using the port, then try again." -ForegroundColor Yellow
        throw
    }

    Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine

    while ($serial.IsOpen) {
        try {
            $line = $serial.ReadLine().Trim()
            if (-not $line) {
                continue
            }

            $lastLine = $line
            $parsed = Parse-ParameterLine $line
            if ($null -ne $parsed) {
                $latest = $parsed
                $lastParameterAt = Get-Date
                Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine
            } elseif ($ShowRaw) {
                Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine
            }
        } catch [System.TimeoutException] {
            Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine
        } catch [System.Management.Automation.MethodInvocationException] {
            if ($_.Exception.InnerException -is [System.TimeoutException]) {
                Show-Dashboard $latest $resolvedPort $BaudRate $startedAt $lastParameterAt $lastLine
            } else {
                throw
            }
        }
    }
} finally {
    if ($null -ne $serial -and $serial.IsOpen) {
        $serial.Close()
    }
}
