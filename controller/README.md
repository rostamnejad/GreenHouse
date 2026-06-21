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
  `PARAMETERS TIME=21:45:08 JDATE=1405/03/25 TEMP_C=31.20 HUMIDITY=38.10 SOIL_MOISTURE=42.5 SOIL_RAW=2235 PRESSURE_MBAR=863.12 ALTITUDE_M=1332.4 TEMP_STATE=warm HUMIDITY_STATE=low_humidity SOIL_STATE=soil_good STATE=warning`
- `GET /status` returns the latest values as plain text.
- `ALTITUDE_M` is a barometric estimate from BMP280 pressure using sea-level pressure `1013.25 mbar`; weather changes can move it.

WiFi addressing:
- Give the controller a stable IP so sensor boards do not lose it after DHCP changes.
- Set `WIFI_STATIC_IP`, `WIFI_SUBNET_MASK`, `WIFI_GATEWAY`, and optionally `WIFI_DNS` in the controller board's local `secrets.py`.
- Set the same controller IP in the sensor board's local `secrets.py` as `CONTROLLER_HOST`.

RGB climate state:
- The RGB status LED uses a dim slow pulse to avoid eye strain.
- Soft green pulse: temperature and humidity are both in the healthy range.
- Soft orange/blue/red pulse: one reading needs attention.
- Slow red pulse: sensor board is not sending data, the last reading is stale, or an alert is active.
- Telegram sent/failed indicators use a short soft pulse, then RGB returns to live status mode.
- Temperature and humidity use independent RGB status colors.
- Temperature: cold is blue/cyan, warm is orange, hot is red.
- Humidity: warning dry/low/high is yellow, critical dry or too humid is red.
- Soil moisture: wet warning is yellow, dry/critical/too wet is red.
- If multiple readings need attention, the RGB shows the most severe condition instead of rapid color switching.
- Sensor timeout: if no reading arrives for 90 seconds, controller reports `sensor_lost`.
- Mixed greenhouse profile: aloe/sansevieria plus citrus and young palms.
- Temperature good range: 18-27 C; day target shown in Telegram: 22-27 C.
- Humidity target: 45-55%; attention above 60%; mold/fungus risk above 70%.

OLED status display:
- The controller supports a 0.96 inch SSD1306 SPI OLED with pins labeled `GND VCC D0 D1 RES DC CS`.
- The OLED shows startup/connectivity steps, then a compact live status page for temperature, air humidity, soil moisture, pressure, and state.
- The OLED is monochrome, so it cannot draw RGB colors. Warning/error rows stay plain and show a status dot beside the affected value: warning is a small steady dot and alert is a larger blinking dot.
- `GET /status` includes `temp_color`, `humidity_color`, `soil_color`, and `status_color` as RGB values for a color UI.
- Recommended wiring:
  `GND -> GND`, `VCC -> 3V3`, `D0 -> GPIO12`, `D1 -> GPIO11`, `RES -> GPIO9`, `DC -> GPIO10`, `CS -> GPIO8`.
- Upload `net_http.py`, `ssd1306.py`, and `oled_display.py` to the controller board along with `main.py` when installing manually.
- Change the `OLED_*` values in local `secrets.py` if you use different pins.
- Set `OLED_ENABLED = False` to run without the display.

Soil moisture sensor:
- Soil moisture is optional and is disabled by default so an unconnected or uncalibrated probe cannot show `100%` and force `STATE=ALERT`.
- If the OLED shows `SOIL 100.0%` without a real calibrated probe, send `/soil_off` in Telegram or remove `soil_enabled.txt` from the controller board, then reboot.
- The sensor board supports a capacitive soil moisture sensor v2.0 with pins labeled `GND VCC AOUT`.
- Recommended wiring on the sensor board:
  `GND -> GND`, `VCC -> 3V3`, `AOUT -> GPIO34`.
- GPIO34 is an ADC1 input pin on classic ESP32 boards, so it works while WiFi is active.
- Calibrate `SOIL_DRY_RAW` and `SOIL_WET_RAW` in the sensor board's local `secrets.py` after installation.

Telegram notifications:
- Add `TELEGRAM_ENABLED = True`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` to the controller board's local `secrets.py`.
- Telegram report sections use professional Persian text with colored emoji markers: green is healthy, orange needs attention, red needs immediate checking.
- Telegram is currently monitor-only: messages provide manual guidance and do not imply that a fan, heater, or humidifier was switched.
- Telegram sends a warning/alert message when temperature or humidity leaves the mixed-greenhouse profile range.
- It sends a recovery message when the greenhouse returns to healthy range.
- It sends sensor link messages when the sensor board stops sending data or starts sending again.
- Send `/status` or `/report` to the bot to get the latest controller reading on demand.
- `TELEGRAM_ALERT_COOLDOWN_SECONDS` controls repeated warning messages; default is 600 seconds.
- `TELEGRAM_REPORT_INTERVAL_SECONDS` controls healthy periodic reports; default is 3600 seconds. Set it to `0` to disable periodic reports.
- `TELEGRAM_COMMAND_POLL_SECONDS` controls how often the controller checks bot commands; default is 20 seconds.
- `TELEGRAM_SENSOR_WAIT_NOTICE_SECONDS` controls the initial no-sensor notice; default is 90 seconds.
- Telegram and OTA network calls have short timeouts so they cannot freeze the controller loop when internet, Telegram, or GitHub is slow.

Terminal dashboard:
- From the project root, run:
  `powershell -ExecutionPolicy Bypass -File .\tools\Read-GreenHouseSerial.ps1`
- To force a port:
  `powershell -ExecutionPolicy Bypass -File .\tools\Read-GreenHouseSerial.ps1 -Port COM14`

OTA updates from GitHub:
- `boot.py` connects to WiFi, then calls `ota_updater.check_for_updates()`.
- `main.py` reconnects WiFi if needed and also checks for updates shortly after startup, then every `OTA_CHECK_INTERVAL_SECONDS` seconds; default is 300 seconds.
- To force an OTA check without pressing reset, open `http://<controller-ip>/ota`.
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
