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

Telegram notifications:
- Add `TELEGRAM_ENABLED = True`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` to the controller board's local `secrets.py`.
- Telegram sends a warning/alert message when temperature or humidity leaves the healthy range.
- It sends a recovery message when the greenhouse returns to healthy range.
- `TELEGRAM_ALERT_COOLDOWN_SECONDS` controls repeated warning messages; default is 600 seconds.
- `TELEGRAM_REPORT_INTERVAL_SECONDS` controls healthy periodic reports; default is 3600 seconds. Set it to `0` to disable periodic reports.

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
- If this repository is public, boards can read OTA files from `raw.githubusercontent.com` without any GitHub token.
- Keep `GITHUB_TOKEN = ""` and `OTA_REQUIRES_TOKEN = False` on the boards when using a public repository.
- The public repository must never contain real `secrets.py`; `.gitignore` excludes it.

Build an OTA manifest from the project root:
- Set a local signing key:
  `$env:GREENHOUSE_OTA_HMAC_KEY = "long-random-secret"`
- Controller:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-OtaManifest.ps1 -Device controller -Version 1 -RawBaseUrl https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/controller`
- Sensors:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-OtaManifest.ps1 -Device sensors -Version 1 -RawBaseUrl https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/sensors`
- Public repository example:
  `powershell -ExecutionPolicy Bypass -File .\tools\Build-OtaManifest.ps1 -Device controller -Version 2 -RawBaseUrl https://raw.githubusercontent.com/rostamnejad/GreenHouse/master/controller`
