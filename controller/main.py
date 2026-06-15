import math
import socket
import time

import network
from machine import Pin
from neopixel import NeoPixel
from version import APP_VERSION, OTA_CHECK_INTERVAL_SECONDS


RGB_PIN = 48
RGB_COUNT = 1
HTTP_PORT = 80
SEA_LEVEL_PRESSURE_MBAR = 1013.25
PARAMETER_KEYS = (
    "temp_c",
    "humidity",
    "pressure_mbar",
    "altitude_m",
    "sensor_version",
    "hour",
    "minute",
    "jy",
    "jm",
    "jd",
)


class HumidityLight:
    def __init__(self, pin=RGB_PIN, count=RGB_COUNT):
        self.led = NeoPixel(Pin(pin, Pin.OUT), count)
        self.temp_c = None
        self.humidity = None
        self.temperature_label = "waiting"
        self.humidity_label = "waiting"
        self.label = "waiting"
        self.severity = 0
        self.base_color = (40, 40, 40)
        self.updated_ms = time.ticks_ms()
        self.off()

    def off(self):
        self.led[0] = (0, 0, 0)
        self.led.write()

    def show_color(self, color):
        self.led[0] = color
        self.led.write()

    def _temperature_condition(self, value):
        if value is None:
            return "waiting", 0, (40, 40, 40)
        if value < 12:
            return "too_cold", 1.0, (0, 20, 255)
        if value < 18:
            return "cold", 0.6, (0, 150, 255)
        if value <= 28:
            return "temp_good", 0, (0, 190, 40)
        if value <= 32:
            return "warm", 0.45, (255, 170, 0)
        return "hot", 1.0, (255, 0, 0)

    def _humidity_condition(self, value):
        if value is None:
            return "waiting", 0, (40, 40, 40)
        if value < 30:
            return "critical_dry", 1.0, (255, 0, 0)
        if value < 35:
            return "dry", 0.75, (255, 35, 0)
        if value < 45:
            return "low_humidity", 0.45, (255, 115, 0)
        if value <= 70:
            return "humidity_good", 0, (0, 190, 40)
        if value <= 85:
            return "humid", 0.45, (0, 80, 255)
        return "too_humid", 1.0, (190, 0, 255)

    def _mix_conditions(self, temp_color, temp_severity, humidity_color, humidity_severity):
        if self.temp_c is None and self.humidity is None:
            return (40, 40, 40)

        if temp_severity == 0 and humidity_severity == 0:
            return (0, 190, 40)

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
            return (0, 190, 40)

        return (int(red / total), int(green / total), int(blue / total))

    def set_conditions(self, temp_c=None, humidity=None, log=True):
        if temp_c is not None:
            self.temp_c = temp_c
        if humidity is not None:
            self.humidity = humidity
        self.updated_ms = time.ticks_ms()

        temp_label, temp_severity, temp_color = self._temperature_condition(self.temp_c)
        humidity_label, humidity_severity, humidity_color = self._humidity_condition(
            self.humidity
        )

        self.temperature_label = temp_label
        self.humidity_label = humidity_label
        self.severity = max(temp_severity, humidity_severity)
        self.base_color = self._mix_conditions(
            temp_color, temp_severity, humidity_color, humidity_severity
        )

        if self.temp_c is None and self.humidity is None:
            self.label = "waiting"
        elif self.severity == 0:
            self.label = "good"
        elif self.severity >= 0.9:
            self.label = "alert"
        else:
            self.label = "warning"

        if log:
            print(
                "CLIMATE TEMP_C=%s HUMIDITY=%s TEMP_STATE=%s HUMIDITY_STATE=%s STATE=%s"
                % (
                    self.temp_c,
                    self.humidity,
                    self.temperature_label,
                    self.humidity_label,
                    self.label,
                )
            )

    def set_humidity(self, value, log=True):
        self.set_conditions(humidity=value, log=log)

    def _scale(self, color, level):
        return tuple(int(component * level) for component in color)

    def animate(self):
        now = time.ticks_ms()

        if self.temp_c is None and self.humidity is None:
            pulse = 0.08 + 0.12 * (1 + math.sin(now / 700)) / 2
            self.led[0] = self._scale((255, 255, 255), pulse)
        elif self.label == "alert":
            self.led[0] = self.base_color if (now // 300) % 2 == 0 else (0, 0, 0)
        else:
            pulse = 0.12 + (0.42 + 0.18 * self.severity) * (
                1 + math.sin(now / 850)
            ) / 2
            self.led[0] = self._scale(self.base_color, pulse)

        self.led.write()


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    return wlan


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

        for key in ("temp_c", "humidity", "pressure_mbar", "altitude_m"):
            if key in query:
                parameters[key] = float(query[key])

        for key in ("sensor_version", "hour", "minute", "jy", "jm", "jd"):
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


def status_body(parameters, light):
    time_value = "--:--"
    if parameters["hour"] is not None and parameters["minute"] is not None:
        time_value = "%02d:%02d" % (parameters["hour"], parameters["minute"])

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
        "time=%s jdate=%s temp_c=%s humidity=%s pressure_mbar=%s altitude_m=%s "
        "controller_version=%d sensor_version=%s temp_state=%s humidity_state=%s state=%s"
        % (
            time_value,
            date_value,
            temp_value,
            humidity_value,
            pressure_value,
            altitude_value,
            APP_VERSION,
            sensor_version,
            light.temperature_label,
            light.humidity_label,
            light.label,
        )
    )


def print_serial_parameters(parameters, light):
    parts = []

    if parameters["hour"] is not None and parameters["minute"] is not None:
        parts.append("TIME=%02d:%02d" % (parameters["hour"], parameters["minute"]))

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

    if parameters["pressure_mbar"] is not None:
        parts.append("PRESSURE_MBAR=%.2f" % parameters["pressure_mbar"])

    if parameters["altitude_m"] is not None:
        parts.append("ALTITUDE_M=%.1f" % parameters["altitude_m"])

    parts.append("CONTROLLER_VERSION=%d" % APP_VERSION)
    if parameters["sensor_version"] is not None:
        parts.append("SENSOR_VERSION=%d" % parameters["sensor_version"])

    parts.append("TEMP_STATE=%s" % light.temperature_label)
    parts.append("HUMIDITY_STATE=%s" % light.humidity_label)
    parts.append("STATE=%s" % light.label)
    print("PARAMETERS " + " ".join(parts))


def ota_status(light, event, local_version, remote_version, path):
    print("OTA_STATUS", event, local_version, remote_version, path)
    if event == "checking":
        light.show_color((0, 30, 80))
    elif event == "up_to_date":
        light.show_color((0, 80, 25))
    elif event in ("update_available", "downloading", "installing"):
        light.show_color((90, 0, 160))
    elif event == "installed":
        light.show_color((0, 160, 40))
    elif event == "disabled":
        pass


def check_ota_periodic(light):
    try:
        import ota_updater

        ota_updater.check_for_updates(
            current_version=APP_VERSION,
            status_callback=lambda event, local, remote, path: ota_status(
                light, event, local, remote, path
            ),
        )
    except Exception as exc:
        print("OTA_ERROR", repr(exc))
        light.show_color((160, 0, 0))


def ota_check_interval_ms():
    try:
        import secrets

        seconds = getattr(secrets, "OTA_CHECK_INTERVAL_SECONDS", OTA_CHECK_INTERVAL_SECONDS)
    except Exception:
        seconds = OTA_CHECK_INTERVAL_SECONDS

    return int(seconds * 1000)


def show_activation(light):
    print("RGB activation ready")
    for _ in range(8):
        light.show_color((0, 180, 45))
        time.sleep_ms(120)
        light.off()
        time.sleep_ms(120)


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
    wlan = connect_wifi()
    light = HumidityLight()
    parameters = {}
    for key in PARAMETER_KEYS:
        parameters[key] = None

    server = make_server()
    last_ota_check_ms = time.ticks_ms()

    print("Controller humidity RGB server started VERSION=%d" % APP_VERSION)
    if wlan.isconnected():
        print("WiFi OK IP:", wlan.ifconfig()[0])
    else:
        print("WiFi not connected, status:", wlan.status())

    show_activation(light)

    while True:
        light.animate()
        now_ms = time.ticks_ms()
        if time.ticks_diff(now_ms, last_ota_check_ms) >= ota_check_interval_ms():
            check_ota_periodic(light)
            last_ota_check_ms = time.ticks_ms()

        try:
            client, address = server.accept()
        except OSError:
            continue

        try:
            request = client.recv(512).decode()
            path = parse_request_path(request)
            new_parameters = parse_parameters(path)
            if new_parameters is None:
                if request.startswith("GET /status"):
                    send_response(client, "200 OK", status_body(parameters, light))
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

                if parameters["temp_c"] is not None or parameters["humidity"] is not None:
                    light.set_conditions(
                        temp_c=parameters["temp_c"],
                        humidity=parameters["humidity"],
                        log=False,
                    )

                print_serial_parameters(parameters, light)
                send_response(client, "200 OK", status_body(parameters, light))
        except Exception as exc:
            print("REQUEST_ERROR", repr(exc), "from", address)
            try:
                send_response(client, "500 Internal Server Error", "error")
            except Exception:
                pass
        finally:
            client.close()


main()
