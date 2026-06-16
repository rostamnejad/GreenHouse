import time

from machine import Pin, SPI
from ssd1306 import SSD1306_SPI


DEFAULT_WIDTH = 128
DEFAULT_HEIGHT = 64
DEFAULT_REFRESH_MS = 1000
DEFAULT_SPI_ID = 1
DEFAULT_BAUDRATE = 10000000
DEFAULT_SCK_PIN = 12
DEFAULT_MOSI_PIN = 11
DEFAULT_RES_PIN = 9
DEFAULT_DC_PIN = 10
DEFAULT_CS_PIN = 8

SHORT_LABELS = {
    "waiting": "WAIT",
    "sensor_waiting": "WAIT",
    "sensor_lost": "LOST",
    "sensor_ok": "OK",
    "good": "GOOD",
    "warning": "WARN",
    "alert": "ALERT",
    "temp_good": "OK",
    "humidity_good": "OK",
    "too_cold": "COLD!",
    "cold": "COLD",
    "warm": "WARM",
    "hot": "HOT!",
    "critical_dry": "DRY!",
    "dry": "DRY",
    "low_humidity": "LOW",
    "humid": "HUMID",
    "too_humid": "HUMID!",
}


def config_value(name, default):
    try:
        import secrets

        return getattr(secrets, name, default)
    except Exception:
        return default


class OledStatusDisplay:
    def __init__(self, app_version):
        self.app_version = app_version
        self.display = None
        self.available = False
        self.refresh_ms = int(config_value("OLED_REFRESH_MS", DEFAULT_REFRESH_MS))
        self.last_update_ms = 0

        if not config_value("OLED_ENABLED", True):
            print("OLED disabled")
            return

        try:
            width = int(config_value("OLED_WIDTH", DEFAULT_WIDTH))
            height = int(config_value("OLED_HEIGHT", DEFAULT_HEIGHT))
            spi = SPI(
                int(config_value("OLED_SPI_ID", DEFAULT_SPI_ID)),
                baudrate=int(config_value("OLED_BAUDRATE", DEFAULT_BAUDRATE)),
                polarity=0,
                phase=0,
                sck=Pin(int(config_value("OLED_SCK_PIN", DEFAULT_SCK_PIN))),
                mosi=Pin(int(config_value("OLED_MOSI_PIN", DEFAULT_MOSI_PIN))),
            )
            self.display = SSD1306_SPI(
                width,
                height,
                spi,
                Pin(int(config_value("OLED_DC_PIN", DEFAULT_DC_PIN))),
                Pin(int(config_value("OLED_RES_PIN", DEFAULT_RES_PIN))),
                Pin(int(config_value("OLED_CS_PIN", DEFAULT_CS_PIN))),
            )
            self.available = True
            self.show_message("GreenHouse", "OLED ready")
            print(
                "OLED ready SCK=%d MOSI=%d RES=%d DC=%d CS=%d"
                % (
                    int(config_value("OLED_SCK_PIN", DEFAULT_SCK_PIN)),
                    int(config_value("OLED_MOSI_PIN", DEFAULT_MOSI_PIN)),
                    int(config_value("OLED_RES_PIN", DEFAULT_RES_PIN)),
                    int(config_value("OLED_DC_PIN", DEFAULT_DC_PIN)),
                    int(config_value("OLED_CS_PIN", DEFAULT_CS_PIN)),
                )
            )
        except Exception as exc:
            self.available = False
            self.display = None
            print("OLED_ERROR", repr(exc))

    def _clip(self, text):
        return str(text)[: self.display.width // 8]

    def _line(self, row, text):
        self.display.text(self._clip(text), 0, row * 8, 1)

    def _float_value(self, value, digits=1):
        if value is None:
            return "--"
        return ("%0.*f" % (digits, value)).strip()

    def _time_line(self, parameters):
        if parameters.get("hour") is None or parameters.get("minute") is None:
            time_value = "--:--"
        else:
            time_value = "%02d:%02d" % (parameters["hour"], parameters["minute"])

        if (
            parameters.get("jy") is None
            or parameters.get("jm") is None
            or parameters.get("jd") is None
        ):
            return time_value

        return "%s %04d/%02d/%02d" % (
            time_value,
            parameters["jy"],
            parameters["jm"],
            parameters["jd"],
        )

    def _short_label(self, label):
        return SHORT_LABELS.get(label, str(label).upper()[:6])

    def show_message(self, title, message=""):
        if not self.available:
            return

        try:
            self.display.fill(0)
            self._line(0, title)
            self.display.hline(0, 10, self.display.width, 1)
            if message:
                self._line(2, message)
            self.display.show()
        except Exception as exc:
            self.available = False
            print("OLED_ERROR", repr(exc))

    def update(self, parameters, light, force=False):
        if not self.available:
            return

        now = time.ticks_ms()
        if not force and time.ticks_diff(now, self.last_update_ms) < self.refresh_ms:
            return

        try:
            temp = self._float_value(parameters.get("temp_c"), 1)
            humidity = self._float_value(light.humidity, 1)

            self.display.fill(0)
            self._line(1, "TEMP: %s C" % temp)
            self._line(3, "HUM : %s %%" % humidity)
            self.display.show()
            self.last_update_ms = now
        except Exception as exc:
            self.available = False
            print("OLED_ERROR", repr(exc))
