WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Use the controller board's stable IP address.
CONTROLLER_HOST = "YOUR_CONTROLLER_IP"
CONTROLLER_PORT = 80

OTA_DEVICE = "sensors"
OTA_ENABLED = True
OTA_MANIFEST_URL = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/master/sensors/ota_manifest.json"
OTA_HMAC_KEY = "CHANGE_ME_LONG_RANDOM_SECRET_NOT_IN_GITHUB"
OTA_CHECK_INTERVAL_SECONDS = 300

# Keep token empty when using a public signed OTA artifact repository.
GITHUB_TOKEN = ""
OTA_REQUIRES_TOKEN = False

# Keep this False unless you deliberately want OTA to replace boot.py.
OTA_ALLOW_BOOT_UPDATE = False

# Optional capacitive soil moisture sensor v2.0 on an ESP32 ADC1 pin.
# Wiring:
# Sensor GND  -> ESP32 GND
# Sensor VCC  -> ESP32 3V3
# Sensor AOUT -> ESP32 GPIO34
# Keep this on ADC1 pins on classic ESP32 because ADC2 conflicts with WiFi.
SOIL_MOISTURE_ENABLED = False
SOIL_MOISTURE_PIN = 34
SOIL_SAMPLE_COUNT = 8
SOIL_RAW_MIN_VALID = 100
SOIL_RAW_MAX_VALID = 4090
SOIL_DISPLAY_RAW_ONLY = False

# Calibrate these after installation:
# 1. Read SOIL_RAW with the probe in dry soil/air and set SOIL_DRY_RAW.
# 2. Read SOIL_RAW with the probe in wet soil/water and set SOIL_WET_RAW.
# Most capacitive probes read higher when dry and lower when wet.
SOIL_DRY_RAW = 3000
SOIL_WET_RAW = 1200
