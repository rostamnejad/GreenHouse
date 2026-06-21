WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Optional: keep controller IP stable so sensor boards can always find it.
# Pick an address reserved on your router, or outside the router DHCP pool.
WIFI_STATIC_IP = ""
WIFI_SUBNET_MASK = "255.255.255.0"
WIFI_GATEWAY = ""
WIFI_DNS = ""

# Soil moisture is optional and stays off until the probe is installed/calibrated.
# Telegram commands can override the controller state.
SOIL_MOISTURE_ENABLED = False

OTA_DEVICE = "controller"
OTA_ENABLED = True
OTA_MANIFEST_URL = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/master/controller/ota_manifest.json"
OTA_HMAC_KEY = "CHANGE_ME_LONG_RANDOM_SECRET_NOT_IN_GITHUB"
OTA_CHECK_INTERVAL_SECONDS = 300
OTA_REQUEST_TIMEOUT_SECONDS = 8

# Keep token empty when using a public signed OTA artifact repository.
GITHUB_TOKEN = ""
OTA_REQUIRES_TOKEN = False

# Keep this False unless you deliberately want OTA to replace boot.py.
OTA_ALLOW_BOOT_UPDATE = False

# Telegram notifications are disabled until you create a bot and fill these.
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
TELEGRAM_ALERT_COOLDOWN_SECONDS = 600
TELEGRAM_REPORT_INTERVAL_SECONDS = 3600
TELEGRAM_COMMAND_POLL_SECONDS = 20
TELEGRAM_SENSOR_WAIT_NOTICE_SECONDS = 90
TELEGRAM_REQUEST_TIMEOUT_SECONDS = 5
TELEGRAM_FAILURE_BACKOFF_SECONDS = 60
TELEGRAM_SEND_RECOVERY = True

# Optional 0.96 inch SSD1306 SPI OLED.
# Wiring:
# OLED GND -> ESP32-S3 GND
# OLED VCC -> ESP32-S3 3V3
# OLED D0  -> ESP32-S3 GPIO12
# OLED D1  -> ESP32-S3 GPIO11
# OLED RES -> ESP32-S3 GPIO9
# OLED DC  -> ESP32-S3 GPIO10
# OLED CS  -> ESP32-S3 GPIO8
OLED_ENABLED = True
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_SPI_ID = 1
OLED_BAUDRATE = 10000000
OLED_SCK_PIN = 12
OLED_MOSI_PIN = 11
OLED_RES_PIN = 9
OLED_DC_PIN = 10
OLED_CS_PIN = 8
OLED_REFRESH_MS = 1000
