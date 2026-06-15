# Controller Board

Board connected on COM12.

Detected USB identity:
- VID:PID: 303A:4001
- Interface: USB Serial Device (COM12)

Current status:
- No serial console output detected.
- No MicroPython REPL response detected.
- esptool could not connect until the board is manually put in bootloader mode.
- WiFi files are prepared locally but have not been uploaded to the board yet.

Hold BOOT, tap RESET/EN, then release BOOT before uploading firmware or files.

Serial parameter output:
- Sensor board sends readings to `GET /parameters`.
- Controller prints one USB serial line per update, for example:
  `PARAMETERS TIME=21:45 JDATE=1405/03/25 TEMP_C=31.20 HUMIDITY=38.10 PRESSURE_MBAR=863.12 ALTITUDE_M=1332.4 TEMP_STATE=warm HUMIDITY_STATE=low_humidity STATE=warning`
- `GET /status` returns the latest values as plain text.
- `ALTITUDE_M` is a barometric estimate from BMP280 pressure using sea-level pressure `1013.25 mbar`; weather changes can move it.

RGB climate state:
- Green pulse: temperature and humidity are both in the healthy range.
- Yellow/orange/cyan/blue/purple pulse: warning, mixed from the temperature and humidity issue colors.
- Red/purple blinking: alert, at least one parameter is far outside the healthy range.
- Temperature healthy range: 18-28 C.
- Humidity healthy range: 45-70%.

Terminal dashboard:
- From the project root, run:
  `powershell -ExecutionPolicy Bypass -File .\tools\Read-GreenHouseSerial.ps1`
- To force a port:
  `powershell -ExecutionPolicy Bypass -File .\tools\Read-GreenHouseSerial.ps1 -Port COM14`

OTA updates from GitHub:
- `boot.py` connects to WiFi, then calls `ota_updater.check_for_updates()`.
- `main.py` also checks for updates every `OTA_CHECK_INTERVAL_SECONDS` seconds; default is 300 seconds.
- OTA is disabled until `OTA_DEVICE`, `OTA_MANIFEST_URL`, and `OTA_HMAC_KEY` are added to the board's local `secrets.py`.
- The board verifies the HMAC-signed manifest and SHA256 of every downloaded file before installing.
- Every firmware release should bump `version.py` and the OTA manifest `version` to the same number.
- Controller serial output includes `CONTROLLER_VERSION`; sensor readings include `SENSOR_VERSION`.
- Sensor board TM1637 shows `V###` for the current firmware version, `OTA` while checking, and `UPD` while updating.
- Do not commit real `secrets.py`, `OTA_HMAC_KEY`, or `GITHUB_TOKEN`; `.gitignore` excludes them.
- Prefer a separate public artifact repository such as `rostamnejad/GreenHouse-OTA`; keep the main source repository private.
- The public OTA repository must contain only signed firmware artifacts (`version.py`, `main.py`, `ota_updater.py`, `ota_manifest.json`) and no `secrets.py`.
- Keep `GITHUB_TOKEN = ""` and `OTA_REQUIRES_TOKEN = False` on the boards when using public signed artifacts.
- Keep `OTA_ENABLED = False` until the public OTA repository exists and the first bundle has been pushed.

Build an OTA manifest from the project root:
- Set a local signing key:
  `$env:GREENHOUSE_OTA_HMAC_KEY = "long-random-secret"`
- Controller:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-OtaManifest.ps1 -Device controller -Version 1 -RawBaseUrl https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/controller`
- Sensors:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-OtaManifest.ps1 -Device sensors -Version 1 -RawBaseUrl https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/sensors`
- Build a token-free public OTA bundle:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-PublicOtaBundle.ps1 -Version 2 -Owner rostamnejad -Repository GreenHouse-OTA -Branch main`
