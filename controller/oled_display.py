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
        self.clock_source = None
        self.clock_anchor_ms = 0
        self.clock_anchor_seconds = 0

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

    def _line(self, row, text, color=1):
        self.display.text(self._clip(text), 0, row * 8, color)

    def _row(self, row, text, invert=False):
        y = row * 8
        if invert:
            self.display.fill_rect(0, y, self.display.width, 8, 1)
            self.display.text(self._clip(text), 0, y, 0)
        else:
            self.display.text(self._clip(text), 0, y, 1)

    def _float_value(self, value, digits=1):
        if value is None:
            return "--"
        return ("%0.*f" % (digits, value)).strip()

    def _sync_clock(self, parameters, now_ms):
        if parameters.get("hour") is None or parameters.get("minute") is None:
            return

        second = parameters.get("second")
        if second is None:
            second = 0

        source = (parameters["hour"], parameters["minute"], second)
        if source == self.clock_source:
            return

        self.clock_source = source
        self.clock_anchor_ms = now_ms
        self.clock_anchor_seconds = (
            parameters["hour"] * 3600 + parameters["minute"] * 60 + second
        )

    def _time_text(self, now_ms):
        if self.clock_source is None:
            return "--:--:--"

        elapsed = int(time.ticks_diff(now_ms, self.clock_anchor_ms) / 1000)
        total = (self.clock_anchor_seconds + elapsed) % 86400
        hour = total // 3600
        minute = (total % 3600) // 60
        second = total % 60
        return "%02d:%02d:%02d" % (hour, minute, second)

    def _date_text(self, parameters):
        if (
            parameters.get("jy") is None
            or parameters.get("jm") is None
            or parameters.get("jd") is None
        ):
            return "----/--/--"

        return "%04d/%02d/%02d" % (
            parameters["jy"],
            parameters["jm"],
            parameters["jd"],
        )

    def _short_label(self, label):
        return SHORT_LABELS.get(label, str(label).upper()[:6])

    def _metric_row(self, row, name, value, state="", issue=False):
        marker = "!" if issue else " "
        if state:
            text = "%s%s %-6s %s" % (marker, name, value, state)
        else:
            text = "%s%s %s" % (marker, name, value)
        self._row(row, text, issue)

    def _is_temp_issue(self, light):
        return light.temp_c is not None and light.temperature_label != "temp_good"

    def _is_humidity_issue(self, light):
        return light.humidity is not None and light.humidity_label != "humidity_good"

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
            self._sync_clock(parameters, now)
            temp = self._float_value(parameters.get("temp_c"), 1)
            humidity = self._float_value(light.humidity, 1)
            pressure = self._float_value(parameters.get("pressure_mbar"), 0)
            temp_issue = self._is_temp_issue(light)
            humidity_issue = self._is_humidity_issue(light)
            pressure_issue = parameters.get("pressure_mbar") is None
            link_issue = light.sensor_link_label() != "sensor_ok"
            state_issue = light.effective_label() not in ("good", "sensor_ok")

            self.display.fill(0)
            self.display.fill_rect(0, 0, self.display.width, 8, 1)
            self._line(0, "%s  v%d" % (self._time_text(now), self.app_version), 0)
            self._row(1, "DATE %s" % self._date_text(parameters))
            self.display.hline(0, 17, self.display.width, 1)
            self._metric_row(
                3,
                "T",
                "%sC" % temp,
                self._short_label(light.temperature_label),
                temp_issue,
            )
            self._metric_row(
                4,
                "H",
                "%s%%" % humidity,
                self._short_label(light.humidity_label),
                humidity_issue,
            )
            self._metric_row(5, "P", "%smbar" % pressure, "", pressure_issue)
            self._metric_row(
                6, "LINK", self._short_label(light.sensor_link_label()), "", link_issue
            )
            self._metric_row(
                7, "STATE", self._short_label(light.effective_label()), "", state_issue
            )
            self.display.show()
            self.last_update_ms = now
        except Exception as exc:
            self.available = False
            print("OLED_ERROR", repr(exc))
