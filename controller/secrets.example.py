WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

OTA_DEVICE = "controller"
OTA_ENABLED = False
OTA_MANIFEST_URL = "https://raw.githubusercontent.com/YOUR_USER/GreenHouse-OTA/main/controller/ota_manifest.json"
OTA_HMAC_KEY = "CHANGE_ME_LONG_RANDOM_SECRET_NOT_IN_GITHUB"
OTA_CHECK_INTERVAL_SECONDS = 300

# Keep token empty when using a public signed OTA artifact repository.
GITHUB_TOKEN = ""
OTA_REQUIRES_TOKEN = False

# Keep this False unless you deliberately want OTA to replace boot.py.
OTA_ALLOW_BOOT_UPDATE = False
