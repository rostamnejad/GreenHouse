WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

OTA_DEVICE = "sensors"
OTA_MANIFEST_URL = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/sensors/ota_manifest.json"
OTA_HMAC_KEY = "CHANGE_ME_LONG_RANDOM_SECRET_NOT_IN_GITHUB"
OTA_CHECK_INTERVAL_SECONDS = 300

# Only needed for a private repository. Prefer a public signed manifest or a proxy.
GITHUB_TOKEN = ""

# Keep this False unless you deliberately want OTA to replace boot.py.
OTA_ALLOW_BOOT_UPDATE = False
