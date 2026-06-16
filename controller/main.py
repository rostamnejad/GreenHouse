import math
import socket
import time

import network
from machine import Pin
from neopixel import NeoPixel
from telegram_notifier import TelegramNotifier
from version import APP_VERSION, OTA_CHECK_INTERVAL_SECONDS

try:
    from oled_display import OledStatusDisplay
except Exception as exc:
    OledStatusDisplay = None
    OLED_IMPORT_ERROR = exc
else:
    OLED_IMPORT_ERROR = None


RGB_PIN = 48
RGB_COUNT = 1
HTTP_PORT = 80
SEA_LEVEL_PRESSURE_MBAR = 1013.25
SENSOR_STALE_TIMEOUT_SECONDS = 90
SENSOR_LINK_CHECK_INTERVAL_MS = 5000
WIFI_RECONNECT_INTERVAL_MS = 15000
WIFI_CONNECT_TIMEOUT_MS = 10000
OTA_STARTUP_DELAY_MS = 15000
HTTP_CLIENT_TIMEOUT_SECONDS = 2
PARAMETER_KEYS = (
    "temp_c",
    "humidity",
    "soil_moisture",
    "soil_raw",
    "pressure_mbar",
    "altitude_m",
    "sensor_version",
    "hour",
    "minute",
    "second",
    "jy",
    "jm",
    "jd",
)


class HumidityLight:
    def __init__(self, pin=RGB_PIN, count=RGB_COUNT):
        self.led = NeoPixel(Pin(pin, Pin.OUT), count)
        self.temp_c = None
        self.humidity = None
        self.soil_moisture = None
        self.temperature_label = "waiting"
        self.humidity_label = "waiting"
        self.soil_label = "waiting"
        self.label = "waiting"
        self.severity = 0
        self.base_color = (40, 40, 40)
        self.temp_color = (40, 40, 40)
        self.temp_severity = 0
        self.humidity_color = (40, 40, 40)
        self.humidity_severity = 0
        self.soil_color = (40, 40, 40)
        self.soil_severity = 0
        self.updated_ms = time.ticks_ms()
        self.has_reading = False
        self.transient_event = ""
        self.transient_until_ms = 0
        self.off()

    def off(self):
        self.led[0] = (0, 0, 0)
        self.led.write()

    def show_color(self, color):
        self.led[0] = color
        self.led.write()

    def _temperature_condition(self, value):
        if value is None:
            return "waiting", 0, (8, 8, 8)
        if value < 12:
            return "too_cold", 1.0, (0, 15, 110)
        if value < 18:
            return "cold", 0.6, (0, 65, 100)
        if value <= 28:
            return "temp_good", 0, (0, 75, 20)
        if value <= 32:
            return "warm", 0.45, (110, 55, 0)
        return "hot", 1.0, (120, 0, 0)

    def _humidity_condition(self, value):
        if value is None:
            return "waiting", 0, (8, 8, 8)
        if value < 30:
            return "critical_dry", 1.0, (120, 0, 0)
        if value < 35:
            return "dry", 0.65, (90, 74, 0)
        if value < 45:
            return "low_humidity", 0.45, (82, 70, 0)
        if value <= 70:
            return "humidity_good", 0, (0, 75, 20)
        if value <= 85:
            return "humid", 0.45, (82, 70, 0)
        return "too_humid", 1.0, (120, 0, 0)

    def _soil_condition(self, value):
        if value is None:
            return "waiting", 0, (8, 8, 8)
        if value < 15:
            return "soil_critical_dry", 1.0, (120, 0, 0)
        if value < 35:
            return "soil_dry", 1.0, (120, 0, 0)
        if value <= 80:
            return "soil_good", 0, (0, 75, 20)
        if value <= 90:
            return "soil_wet", 0.45, (82, 70, 0)
        return "soil_too_wet", 1.0, (120, 0, 0)

    def _mix_conditions(self, temp_color, temp_severity, humidity_color, humidity_severity):
        if self.temp_c is None and self.humidity is None:
            return (40, 40, 40)

        if temp_severity == 0 and humidity_severity == 0:
            return (0, 200, 0)

        total = 0
        red = 0
        green = 0
        blue = 0

        if self.temp_c is not None:
            weight = max(0.15, temp_severity)
            red += temp_color[0] * weight
            green += temp_color[1] * weight
            blue += temp_color[2] * weight
            total += weight

        if self.humidity is not None:
            weight = max(0.15, humidity_severity)
            red += humidity_color[0] * weight
            green += humidity_color[1] * weight
            blue += humidity_color[2] * weight
            total += weight

        if total == 0:
            return (0, 200, 0)

        return (int(red / total), int(green / total), int(blue / total))

    def set_conditions(self, temp_c=None, humidity=None, soil_moisture=None, log=True):
        if temp_c is not None:
            self.temp_c = temp_c
            self.has_reading = True
        if humidity is not None:
            self.humidity = humidity
            self.has_reading = True
        if soil_moisture is not None:
            self.soil_moisture = soil_moisture
            self.has_reading = True
        self.updated_ms = time.ticks_ms()

        temp_label, temp_severity, temp_color = self._temperature_condition(self.temp_c)
        humidity_label, humidity_severity, humidity_color = self._humidity_condition(
            self.humidity
        )
        soil_label, soil_severity, soil_color = self._soil_condition(self.soil_moisture)

        self.temperature_label = temp_label
        self.humidity_label = humidity_label
        self.soil_label = soil_label
        self.temp_color = temp_color
        self.temp_severity = temp_severity
        self.humidity_color = humidity_color
        self.humidity_severity = humidity_severity
        self.soil_color = soil_color
        self.soil_severity = soil_severity
        self.severity = max(temp_severity, humidity_severity, soil_severity)
        if self.severity == 0:
            self.base_color = (0, 75, 20)
        elif temp_severity >= humidity_severity and temp_severity >= soil_severity:
            self.base_color = temp_color
        elif humidity_severity >= soil_severity:
            self.base_color = humidity_color
        else:
            self.base_color = soil_color

        if self.temp_c is None and self.humidity is None and self.soil_moisture is None:
            self.label = "waiting"
        elif self.severity == 0:
            self.label = "good"
        elif self.severity >= 0.9:
            self.label = "alert"
        else:
            self.label = "warning"

        if log:
            print(
                "CLIMATE TEMP_C=%s HUMIDITY=%s SOIL_MOISTURE=%s TEMP_STATE=%s HUMIDITY_STATE=%s SOIL_STATE=%s STATE=%s"
                % (
                    self.temp_c,
                    self.humidity,
                    self.soil_moisture,
                    self.temperature_label,
                    self.humidity_label,
                    self.soil_label,
                    self.label,
                )
            )

    def set_humidity(self, value, log=True):
        self.set_conditions(humidity=value, log=log)

    def _scale(self, color, level):
        return tuple(int(component * level) for component in color)

    def show_transient(self, event, duration_ms=1500):
        self.transient_event = event
        self.transient_until_ms = time.ticks_ms() + duration_ms

    def _animate_transient(self, now):
        if self.transient_event == "telegram_sent":
            phase = (now // 130) % 8
            self.led[0] = (0, 95, 22) if phase in (0, 2, 4, 6) else (0, 0, 0)
        elif self.transient_event == "telegram_failed":
            phase = (now // 160) % 6
            self.led[0] = (120, 0, 0) if phase in (0, 2) else (0, 0, 0)
        else:
            self.led[0] = (0, 0, 0)

    def sensor_age_seconds(self):
        if not self.has_reading:
            return None
        return int(time.ticks_diff(time.ticks_ms(), self.updated_ms) / 1000)

    def sensor_link_label(self):
        if not self.has_reading:
            return "sensor_waiting"
        if self.sensor_age_seconds() > SENSOR_STALE_TIMEOUT_SECONDS:
            return "sensor_lost"
        return "sensor_ok"

    def effective_label(self):
        sensor_label = self.sensor_link_label()
        if sensor_label != "sensor_ok":
            return sensor_label
        return self.label

    def _animate_sensor_missing(self, now):
        phase = (now // 180) % 12
        if phase in (0, 2):
            self.led[0] = (120, 0, 0)
        elif phase in (1, 3):
            self.led[0] = (0, 0, 0)
        else:
            self.led[0] = (12, 0, 0)

    def _active_condition_colors(self):
        colors = []
        if self.temp_c is not None and self.temp_severity > 0:
            colors.append((self.temp_color, self.temp_severity))
        if self.humidity is not None and self.humidity_severity > 0:
            colors.append((self.humidity_color, self.humidity_severity))
        if self.soil_moisture is not None and self.soil_severity > 0:
            colors.append((self.soil_color, self.soil_severity))
        return colors

    def animate(self):
        now = time.ticks_ms()

        if time.ticks_diff(self.transient_until_ms, now) > 0:
            self._animate_transient(now)
        elif self.sensor_link_label() != "sensor_ok":
            self._animate_sensor_missing(now)
        else:
            condition_colors = self._active_condition_colors()
            if condition_colors:
                if len(condition_colors) == 1:
                    color, severity = condition_colors[0]
                else:
                    color, severity = condition_colors[(now // 900) % len(condition_colors)]

                if severity >= 0.9 and (now // 280) % 2 == 1:
                    self.led[0] = (0, 0, 0)
                else:
                    pulse = 0.18 + 0.72 * (1 + math.sin(now / 650)) / 2
                    self.led[0] = self._scale(color, pulse)
            else:
                pulse = 0.12 + 0.38 * (1 + math.sin(now / 850)) / 2
                self.led[0] = self._scale((0, 75, 20), pulse)

        self.led.write()


def wifi_credentials():
    try:
        import secrets

        return getattr(secrets, "WIFI_SSID", ""), getattr(secrets, "WIFI_PASSWORD", "")
    except Exception:
        return "", ""


def display_step(display, title, message=""):
    if display is not None:
        display.show_step(title, message)


def connect_wifi(display=None, timeout_ms=WIFI_CONNECT_TIMEOUT_MS):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        display_step(display, "WiFi OK", wlan.ifconfig()[0])
        return wlan

    ssid, password = wifi_credentials()
    if not ssid:
        print("WiFi not configured in secrets.py")
        display_step(display, "WiFi config", "missing SSID")
        return wlan

    print("WiFi connecting from main...")
    display_step(display, "WiFi", "connecting...")
    try:
        wlan.connect(ssid, password)
    except Exception as exc:
        print("WiFi connect error:", repr(exc))
        display_step(display, "WiFi error", "connect failed")
        return wlan

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if wlan.isconnected():
            print("WiFi connected from main IP:", wlan.ifconfig()[0])
            display_step(display, "WiFi OK", wlan.ifconfig()[0])
            return wlan
        time.sleep_ms(250)

    print("WiFi connect timeout, status:", wlan.status())
    display_step(display, "WiFi timeout", "status %s" % wlan.status())
    return wlan


def ensure_wifi_connected(wlan, timeout_ms=0, display=None):
    wlan.active(True)
    if wlan.isconnected():
        return True

    ssid, password = wifi_credentials()
    if not ssid:
        print("WiFi reconnect skipped: missing WIFI_SSID")
        display_step(display, "WiFi config", "missing SSID")
        return False

    try:
        print("WiFi reconnecting...")
        display_step(display, "WiFi", "reconnecting...")
        wlan.connect(ssid, password)
    except Exception as exc:
        print("WiFi reconnect error:", repr(exc))
        display_step(display, "WiFi error", "reconnect failed")
        return False

    if timeout_ms <= 0:
        return wlan.isconnected()

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if wlan.isconnected():
            print("WiFi reconnected IP:", wlan.ifconfig()[0])
            display_step(display, "WiFi OK", wlan.ifconfig()[0])
            return True
        time.sleep_ms(250)

    print("WiFi reconnect timeout, status:", wlan.status())
    display_step(display, "WiFi timeout", "status %s" % wlan.status())
    return wlan.isconnected()


def parse_request_path(request):
    first_line = request.split("\r\n", 1)[0]
    parts = first_line.split(" ")
    if len(parts) < 2:
        return None

    return parts[1]


def parse_query(path):
    if "?" not in path:
        return {}

    query = path.split("?", 1)[1]
    values = {}
    for item in query.split("&"):
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value

    return values


def parse_parameters(path):
    if path is None:
        return None

    if not path.startswith("/humidity?"):
        if not path.startswith("/parameters?"):
            return None

        query = parse_query(path)
        parameters = {}

        for key in (
            "temp_c",
            "humidity",
            "soil_moisture",
            "pressure_mbar",
            "altitude_m",
        ):
            if key in query:
                parameters[key] = float(query[key])

        for key in (
            "sensor_version",
            "soil_raw",
            "hour",
            "minute",
            "second",
            "jy",
            "jm",
            "jd",
        ):
            if key in query:
                parameters[key] = int(query[key])

        return parameters if parameters else None

    query = parse_query(path)
    if "value" in query:
        return {"humidity": float(query["value"])}

    return None


def pressure_to_altitude_m(pressure_mbar):
    if pressure_mbar is None or pressure_mbar <= 0:
        return None
    return 44330 * (1 - (pressure_mbar / SEA_LEVEL_PRESSURE_MBAR) ** 0.1903)


def rgb_text(color):
    return "%d,%d,%d" % color


def status_body(parameters, light):
    time_value = "--:--"
    if parameters["hour"] is not None and parameters["minute"] is not None:
        second = parameters["second"] if parameters["second"] is not None else 0
        time_value = "%02d:%02d:%02d" % (
            parameters["hour"],
            parameters["minute"],
            second,
        )

    date_value = "----/--/--"
    if (
        parameters["jy"] is not None
        and parameters["jm"] is not None
        and parameters["jd"] is not None
    ):
        date_value = "%04d/%02d/%02d" % (
            parameters["jy"],
            parameters["jm"],
            parameters["jd"],
        )

    temp_value = "None"
    if parameters["temp_c"] is not None:
        temp_value = "%.2f" % parameters["temp_c"]

    humidity_value = "None"
    if light.humidity is not None:
        humidity_value = "%.2f" % light.humidity

    soil_value = "None"
    if light.soil_moisture is not None:
        soil_value = "%.1f" % light.soil_moisture

    soil_raw_value = "None"
    if parameters["soil_raw"] is not None:
        soil_raw_value = "%d" % parameters["soil_raw"]

    pressure_value = "None"
    if parameters["pressure_mbar"] is not None:
        pressure_value = "%.2f" % parameters["pressure_mbar"]

    altitude_value = "None"
    if parameters["altitude_m"] is not None:
        altitude_value = "%.1f" % parameters["altitude_m"]

    sensor_version = "None"
    if parameters["sensor_version"] is not None:
        sensor_version = "%d" % parameters["sensor_version"]

    return (
        "time=%s jdate=%s temp_c=%s humidity=%s soil_moisture=%s soil_raw=%s "
        "pressure_mbar=%s altitude_m=%s "
        "controller_version=%d sensor_version=%s temp_state=%s humidity_state=%s "
        "soil_state=%s temp_color=%s humidity_color=%s soil_color=%s status_color=%s "
        "sensor_link=%s sensor_age_s=%s state=%s"
        % (
            time_value,
            date_value,
            temp_value,
            humidity_value,
            soil_value,
            soil_raw_value,
            pressure_value,
            altitude_value,
            APP_VERSION,
            sensor_version,
            light.temperature_label,
            light.humidity_label,
            light.soil_label,
            rgb_text(light.temp_color),
            rgb_text(light.humidity_color),
            rgb_text(light.soil_color),
            rgb_text(light.base_color),
            light.sensor_link_label(),
            light.sensor_age_seconds(),
            light.effective_label(),
        )
    )


def print_serial_parameters(parameters, light):
    parts = []

    if parameters["hour"] is not None and parameters["minute"] is not None:
        second = parameters["second"] if parameters["second"] is not None else 0
        parts.append(
            "TIME=%02d:%02d:%02d"
            % (parameters["hour"], parameters["minute"], second)
        )

    if (
        parameters["jy"] is not None
        and parameters["jm"] is not None
        and parameters["jd"] is not None
    ):
        parts.append(
            "JDATE=%04d/%02d/%02d"
            % (parameters["jy"], parameters["jm"], parameters["jd"])
        )

    if parameters["temp_c"] is not None:
        parts.append("TEMP_C=%.2f" % parameters["temp_c"])

    if light.humidity is not None:
        parts.append("HUMIDITY=%.2f" % light.humidity)

    if light.soil_moisture is not None:
        parts.append("SOIL_MOISTURE=%.1f" % light.soil_moisture)

    if parameters["soil_raw"] is not None:
        parts.append("SOIL_RAW=%d" % parameters["soil_raw"])

    if parameters["pressure_mbar"] is not None:
        parts.append("PRESSURE_MBAR=%.2f" % parameters["pressure_mbar"])

    if parameters["altitude_m"] is not None:
        parts.append("ALTITUDE_M=%.1f" % parameters["altitude_m"])

    parts.append("CONTROLLER_VERSION=%d" % APP_VERSION)
    if parameters["sensor_version"] is not None:
        parts.append("SENSOR_VERSION=%d" % parameters["sensor_version"])

    parts.append("TEMP_STATE=%s" % light.temperature_label)
    parts.append("HUMIDITY_STATE=%s" % light.humidity_label)
    parts.append("SOIL_STATE=%s" % light.soil_label)
    parts.append("SENSOR_LINK=%s" % light.sensor_link_label())
    if light.sensor_age_seconds() is not None:
        parts.append("SENSOR_AGE_S=%d" % light.sensor_age_seconds())
    parts.append("STATE=%s" % light.effective_label())
    print("PARAMETERS " + " ".join(parts))


def ota_status(light, display, event, local_version, remote_version, path):
    print("OTA_STATUS", event, local_version, remote_version, path)
    if event == "checking":
        display_step(display, "OTA", "checking...")
        light.show_color((0, 12, 42))
    elif event == "up_to_date":
        display_step(display, "OTA OK", "v%d" % local_version)
        light.show_color((0, 55, 12))
    elif event in ("update_available", "downloading", "installing"):
        display_step(display, "OTA %s" % event[:6], path or "v%d" % remote_version)
        light.show_color((42, 0, 70))
    elif event == "installed":
        display_step(display, "OTA done", "resetting...")
        light.show_color((0, 75, 20))
    elif event == "disabled":
        display_step(display, "OTA disabled", "")
        pass


def check_ota_periodic(light, wlan=None, display=None):
    try:
        if wlan is not None and not ensure_wifi_connected(
            wlan, timeout_ms=WIFI_CONNECT_TIMEOUT_MS, display=display
        ):
            print("OTA_ERROR WiFi is not connected")
            display_step(display, "OTA error", "no WiFi")
            light.show_color((100, 0, 0))
            return

        import ota_updater

        ota_updater.check_for_updates(
            current_version=APP_VERSION,
            status_callback=lambda event, local, remote, path: ota_status(
                light, display, event, local, remote, path
            ),
        )
    except Exception as exc:
        print("OTA_ERROR", repr(exc))
        display_step(display, "OTA error", "check serial")
        light.show_color((100, 0, 0))


def ota_check_interval_ms():
    try:
        import secrets

        seconds = getattr(secrets, "OTA_CHECK_INTERVAL_SECONDS", OTA_CHECK_INTERVAL_SECONDS)
    except Exception:
        seconds = OTA_CHECK_INTERVAL_SECONDS

    return int(seconds * 1000)


def next_ota_check_ms(delay_ms=None):
    if delay_ms is None:
        delay_ms = ota_check_interval_ms()
    return time.ticks_add(time.ticks_ms(), int(delay_ms))


def show_activation(light):
    print("RGB activation ready")
    for _ in range(8):
        light.show_color((0, 80, 20))
        time.sleep_ms(120)
        light.off()
        time.sleep_ms(120)


def telegram_status(light, event):
    if event == "sent":
        light.show_transient("telegram_sent")
    elif event == "failed":
        light.show_transient("telegram_failed")


def make_display(app_version):
    if OledStatusDisplay is None:
        print("OLED_IMPORT_ERROR", repr(OLED_IMPORT_ERROR))
        return None
    return OledStatusDisplay(app_version)


def update_display(display, parameters, light, force=False):
    if display is not None:
        display.update(parameters, light, force=force)


def make_server(port=HTTP_PORT):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(2)
    server.settimeout(0.15)
    return server


def send_response(client, status, body):
    payload = body + "\n"
    response = (
        "HTTP/1.0 %s\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s"
    ) % (status, len(payload), payload)
    client.send(response.encode())


def main():
    light = HumidityLight()
    parameters = {}
    for key in PARAMETER_KEYS:
        parameters[key] = None
    display = make_display(APP_VERSION)
    display_step(display, "Boot", "starting...")
    wlan = connect_wifi(display=display)

    telegram = TelegramNotifier(
        APP_VERSION,
        status_callback=lambda event: telegram_status(light, event),
    )
    display_step(display, "Server", "starting...")
    server = make_server()
    display_step(display, "Server OK", "port %d" % HTTP_PORT)
    next_ota_ms = next_ota_check_ms(OTA_STARTUP_DELAY_MS)
    last_wifi_reconnect_ms = time.ticks_ms()
    last_telegram_poll_ms = time.ticks_ms()
    last_sensor_link_check_ms = time.ticks_ms()

    print("Controller humidity RGB server started VERSION=%d" % APP_VERSION)
    if wlan.isconnected():
        print("WiFi OK IP:", wlan.ifconfig()[0])
        if display is not None:
            display.show_message("WiFi OK", wlan.ifconfig()[0])
    else:
        print("WiFi not connected, status:", wlan.status())
        if display is not None:
            display.show_message("WiFi error", "status %s" % wlan.status())

    show_activation(light)
    display_step(display, "Sensor", "waiting...")
    update_display(display, parameters, light, force=True)

    while True:
        light.animate()
        update_display(display, parameters, light)
        now_ms = time.ticks_ms()
        if (
            not wlan.isconnected()
            and time.ticks_diff(now_ms, last_wifi_reconnect_ms)
            >= WIFI_RECONNECT_INTERVAL_MS
        ):
            ensure_wifi_connected(wlan, timeout_ms=0, display=display)
            last_wifi_reconnect_ms = now_ms

        if time.ticks_diff(now_ms, next_ota_ms) >= 0:
            check_ota_periodic(light, wlan, display)
            next_ota_ms = next_ota_check_ms()

        if (
            time.ticks_diff(now_ms, last_telegram_poll_ms)
            >= telegram.command_poll_interval_ms()
        ):
            telegram.poll_commands(parameters, light)
            last_telegram_poll_ms = time.ticks_ms()

        if (
            time.ticks_diff(now_ms, last_sensor_link_check_ms)
            >= SENSOR_LINK_CHECK_INTERVAL_MS
        ):
            telegram.monitor_sensor_link(parameters, light)
            last_sensor_link_check_ms = time.ticks_ms()

        force_ota = False
        try:
            client, address = server.accept()
        except OSError:
            continue

        try:
            try:
                client.settimeout(HTTP_CLIENT_TIMEOUT_SECONDS)
            except Exception:
                pass

            request = client.recv(512).decode()
            path = parse_request_path(request)
            new_parameters = parse_parameters(path)
            if new_parameters is None:
                if request.startswith("GET /status"):
                    send_response(client, "200 OK", status_body(parameters, light))
                elif request.startswith("GET /ota"):
                    send_response(client, "200 OK", "ota check requested")
                    force_ota = True
                else:
                    send_response(client, "404 Not Found", "not found")
            else:
                for key in new_parameters:
                    parameters[key] = new_parameters[key]

                if (
                    parameters["altitude_m"] is None
                    and parameters["pressure_mbar"] is not None
                ):
                    parameters["altitude_m"] = pressure_to_altitude_m(
                        parameters["pressure_mbar"]
                    )

                if (
                    parameters["temp_c"] is not None
                    or parameters["humidity"] is not None
                    or parameters["soil_moisture"] is not None
                ):
                    light.set_conditions(
                        temp_c=parameters["temp_c"],
                        humidity=parameters["humidity"],
                        soil_moisture=parameters["soil_moisture"],
                        log=False,
                    )

                update_display(display, parameters, light, force=True)
                print_serial_parameters(parameters, light)
                send_response(client, "200 OK", status_body(parameters, light))
                telegram.update(parameters, light)
        except Exception as exc:
            print("REQUEST_ERROR", repr(exc), "from", address)
            try:
                send_response(client, "500 Internal Server Error", "error")
            except Exception:
                pass
        finally:
            client.close()

        if force_ota:
            check_ota_periodic(light, wlan, display)
            next_ota_ms = next_ota_check_ms()


main()
