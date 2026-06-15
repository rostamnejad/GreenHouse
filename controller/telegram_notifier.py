import time


DEFAULT_ALERT_COOLDOWN_SECONDS = 600
DEFAULT_REPORT_INTERVAL_SECONDS = 3600
DEFAULT_COMMAND_POLL_SECONDS = 20
DEFAULT_SENSOR_WAIT_NOTICE_SECONDS = 90
REQUEST_USER_AGENT = "GreenHouse-Telegram"
TEMP_MIN_C = 18.0
TEMP_MAX_C = 28.0
HUMIDITY_MIN_PERCENT = 45.0
HUMIDITY_MAX_PERCENT = 70.0
LABEL_TEXT = {
    "waiting": "waiting",
    "too_cold": "too cold",
    "cold": "cold",
    "temp_good": "good",
    "warm": "warm",
    "hot": "hot",
    "critical_dry": "critical dry",
    "dry": "dry",
    "low_humidity": "low humidity",
    "humidity_good": "good",
    "humid": "humid",
    "too_humid": "too humid",
}
STATE_ICON = {
    "good": "🟢",
    "warning": "🟠",
    "alert": "🔴",
    "sensor_waiting": "🟡",
    "sensor_lost": "🔴",
    "waiting": "⚪",
}
LABEL_ICON = {
    "waiting": "⚪",
    "too_cold": "🔴",
    "cold": "🟠",
    "temp_good": "🟢",
    "warm": "🟠",
    "hot": "🔴",
    "critical_dry": "🔴",
    "dry": "🟠",
    "low_humidity": "🟠",
    "humidity_good": "🟢",
    "humid": "🟠",
    "too_humid": "🔴",
}


def _quote(value):
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    parts = []
    for byte in str(value).encode("utf-8"):
        char = chr(byte)
        if char in safe:
            parts.append(char)
        else:
            parts.append("%%%02X" % byte)
    return "".join(parts)


def _html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _pre(text):
    return "<pre>" + _html_escape(text) + "</pre>"


def _value(parameters, key, empty="None"):
    value = parameters.get(key)
    if value is None:
        return empty
    return value


def _fmt(value, digits=2, empty="--"):
    if value is None:
        return empty
    return ("%." + str(digits) + "f") % value


def _label(label):
    return LABEL_TEXT.get(label, label)


def _state_icon(state):
    return STATE_ICON.get(state, "⚪")


def _label_icon(label):
    return LABEL_ICON.get(label, "⚪")


def _range_position(value, low, high, unit):
    if value is None:
        return "no reading"
    if value < low:
        return "%.2f %s below min" % (low - value, unit)
    if value > high:
        return "%.2f %s above max" % (value - high, unit)
    return "inside range"


def _value_action(name, value, low, high, unit):
    if value is None:
        return "Wait for %s reading." % name
    if value < low:
        return "Raise %s by about %.1f %s." % (name, low - value, unit)
    if value > high:
        return "Reduce %s by about %.1f %s." % (name, value - high, unit)
    return ""


def _required_actions(parameters):
    actions = []
    temp_action = _value_action(
        "temperature",
        parameters.get("temp_c"),
        TEMP_MIN_C,
        TEMP_MAX_C,
        "C",
    )
    humidity_action = _value_action(
        "humidity",
        parameters.get("humidity"),
        HUMIDITY_MIN_PERCENT,
        HUMIDITY_MAX_PERCENT,
        "%",
    )

    for action in (temp_action, humidity_action):
        if action:
            actions.append(action)

    if parameters.get("temp_c") is not None and parameters.get("humidity") is not None:
        if not actions:
            return ["No immediate action.", "Keep monitoring."]

    return actions if actions else ["Wait for sensor reading."]


def _action_lines(parameters):
    lines = []
    actions = _required_actions(parameters)
    for index, action in enumerate(actions):
        icon = "✅" if action.startswith("No immediate") else "🔧"
        if action.startswith("Keep"):
            icon = "✅"
        if action.startswith("Wait for"):
            icon = "🟡"
        lines.append("%d. %s %s" % (index + 1, icon, action))
    return lines


def _effective_state(light):
    if hasattr(light, "effective_label"):
        return light.effective_label()
    return light.label


def _sensor_link(light):
    if hasattr(light, "sensor_link_label"):
        return light.sensor_link_label()
    return "sensor_ok"


def _sensor_age(light):
    if hasattr(light, "sensor_age_seconds"):
        return light.sensor_age_seconds()
    return None


class TelegramNotifier:
    def __init__(self, controller_version, status_callback=None):
        self.controller_version = controller_version
        self.status_callback = status_callback
        self.disabled_logged = False
        self.last_alert_ms = None
        self.last_report_ms = time.ticks_ms()
        self.last_state = "waiting"
        self.last_issue_key = ""
        self.last_sensor_link = None
        self.sensor_wait_started_ms = time.ticks_ms()
        self.sensor_wait_notice_sent = False

    def _notify(self, event):
        if self.status_callback is None:
            return
        try:
            self.status_callback(event)
        except Exception as exc:
            print("TELEGRAM_STATUS_CALLBACK_ERROR", repr(exc))

    def _config(self):
        try:
            import secrets
        except Exception:
            return None

        enabled = getattr(secrets, "TELEGRAM_ENABLED", False)
        token = getattr(secrets, "TELEGRAM_BOT_TOKEN", "")
        chat_id = getattr(secrets, "TELEGRAM_CHAT_ID", "")
        if not enabled:
            return None

        if not token or not chat_id:
            if not self.disabled_logged:
                print("TELEGRAM disabled: missing bot token or chat id")
                self.disabled_logged = True
            return None

        return {
            "token": token,
            "chat_id": chat_id,
            "alert_cooldown_ms": int(
                getattr(
                    secrets,
                    "TELEGRAM_ALERT_COOLDOWN_SECONDS",
                    DEFAULT_ALERT_COOLDOWN_SECONDS,
                )
            )
            * 1000,
            "report_interval_ms": int(
                getattr(
                    secrets,
                    "TELEGRAM_REPORT_INTERVAL_SECONDS",
                    DEFAULT_REPORT_INTERVAL_SECONDS,
                )
            )
            * 1000,
            "send_recovery": getattr(secrets, "TELEGRAM_SEND_RECOVERY", True),
            "command_poll_ms": int(
                getattr(
                    secrets,
                    "TELEGRAM_COMMAND_POLL_SECONDS",
                    DEFAULT_COMMAND_POLL_SECONDS,
                )
            )
            * 1000,
            "sensor_wait_notice_ms": int(
                getattr(
                    secrets,
                    "TELEGRAM_SENSOR_WAIT_NOTICE_SECONDS",
                    DEFAULT_SENSOR_WAIT_NOTICE_SECONDS,
                )
            )
            * 1000,
        }

    def _requests(self):
        try:
            import urequests as requests
        except ImportError:
            import requests

        return requests

    def _load_json(self, data):
        try:
            import ujson as json
        except ImportError:
            import json

        if isinstance(data, bytes):
            data = data.decode()
        return json.loads(data)

    def _api_get_json(self, config, method, query):
        requests = self._requests()
        url = "https://api.telegram.org/bot%s/%s?%s" % (
            config["token"],
            method,
            query,
        )
        response = requests.get(url, headers={"User-Agent": REQUEST_USER_AGENT})
        try:
            status = getattr(response, "status_code", 200)
            data = getattr(response, "content", b"")
            if status != 200:
                print("TELEGRAM_HTTP", method, status)
                return None

            payload = self._load_json(data)
            if not payload.get("ok"):
                print("TELEGRAM_API_ERROR", method, payload.get("description", ""))
                return None

            return payload
        finally:
            try:
                response.close()
            except Exception:
                pass

    def _send(self, config, text):
        requests = self._requests()
        url = (
            "https://api.telegram.org/bot%s/sendMessage?chat_id=%s&parse_mode=HTML&text=%s"
            % (config["token"], _quote(config["chat_id"]), _quote(text))
        )
        try:
            response = requests.get(url, headers={"User-Agent": REQUEST_USER_AGENT})
        except Exception as exc:
            print("TELEGRAM_SEND_ERROR", repr(exc))
            self._notify("failed")
            return False

        try:
            status = getattr(response, "status_code", 200)
            if status == 200:
                print("TELEGRAM_SEND_OK")
                self._notify("sent")
                return True
            print("TELEGRAM_SEND_HTTP", status)
            self._notify("failed")
        finally:
            try:
                response.close()
            except Exception:
                pass
        return False

    def _message(self, title, parameters, light):
        sensor_link = _sensor_link(light)
        sensor_age = _sensor_age(light)
        state = _effective_state(light)
        state_icon = _state_icon(state)

        if sensor_link != "sensor_ok":
            age_text = "--" if sensor_age is None else "%d s" % sensor_age
            return (
                "%s <b>GreenHouse %s</b>\n"
                % (state_icon, _html_escape(title))
            ) + _pre(
                "State       : %s\n"
                "Sensor link : %s\n"
                "Last reading: %s\n"
                "\n"
                "🔴 SENSOR LINK PROBLEM\n"
                "1. 🔧 Check sensor board power.\n"
                "2. 🔧 Check sensor board WiFi.\n"
                "3. 🔧 Reset sensor board if needed.\n"
                "\n"
                "Controller  : v%d"
                % (state.upper(), sensor_link, age_text, self.controller_version)
            )

        time_value = "--:--"
        if parameters.get("hour") is not None and parameters.get("minute") is not None:
            time_value = "%02d:%02d" % (parameters["hour"], parameters["minute"])

        date_value = "----/--/--"
        if (
            parameters.get("jy") is not None
            and parameters.get("jm") is not None
            and parameters.get("jd") is not None
        ):
            date_value = "%04d/%02d/%02d" % (
                parameters["jy"],
                parameters["jm"],
                parameters["jd"],
            )

        sensor_version = _value(parameters, "sensor_version")
        temp_value = parameters.get("temp_c")
        humidity_value = parameters.get("humidity")
        temp_icon = _label_icon(light.temperature_label)
        humidity_icon = _label_icon(light.humidity_label)
        temp_check = "OK" if light.temperature_label == "temp_good" else "CHECK"
        humidity_check = (
            "OK" if light.humidity_label == "humidity_good" else "CHECK"
        )
        pressure_icon = "🔵"
        action_lines = _action_lines(parameters)

        return (
            "%s <b>GreenHouse %s</b>\n"
            % (state_icon, _html_escape(title))
        ) + _pre(
            "State       : %s\n"
            "Updated     : %s  %s\n"
            "\n"
            "%s TEMPERATURE %s\n"
            "Value       : %s C\n"
            "Healthy     : %.0f-%.0f C\n"
            "Status      : %s %s\n"
            "Position    : %s %s\n"
            "\n"
            "%s HUMIDITY %s\n"
            "Value       : %s %%\n"
            "Healthy     : %.0f-%.0f %%\n"
            "Status      : %s %s\n"
            "Position    : %s %s\n"
            "\n"
            "%s PRESSURE\n"
            "Value       : %s mbar\n"
            "Altitude    : %s m\n"
            "\n"
            "🛠 REQUIRED ACTION\n"
            "%s\n"
            "\n"
            "VERSIONS\n"
            "Controller  : v%d\n"
            "Sensor      : v%s"
            % (
                state.upper(),
                time_value,
                date_value,
                temp_icon,
                temp_check,
                _fmt(temp_value),
                TEMP_MIN_C,
                TEMP_MAX_C,
                temp_icon,
                _label(light.temperature_label),
                temp_icon,
                _range_position(temp_value, TEMP_MIN_C, TEMP_MAX_C, "C"),
                humidity_icon,
                humidity_check,
                _fmt(humidity_value),
                HUMIDITY_MIN_PERCENT,
                HUMIDITY_MAX_PERCENT,
                humidity_icon,
                _label(light.humidity_label),
                humidity_icon,
                _range_position(
                    humidity_value,
                    HUMIDITY_MIN_PERCENT,
                    HUMIDITY_MAX_PERCENT,
                    "%",
                ),
                pressure_icon,
                _fmt(parameters.get("pressure_mbar")),
                _fmt(parameters.get("altitude_m"), 1),
                "\n".join(action_lines),
                self.controller_version,
                sensor_version,
            )
        )

    def update(self, parameters, light):
        try:
            self._update(parameters, light)
        except Exception as exc:
            print("TELEGRAM_ERROR", repr(exc))

    def command_poll_interval_ms(self):
        config = self._config()
        if config is None:
            return DEFAULT_COMMAND_POLL_SECONDS * 1000
        return max(5000, config["command_poll_ms"])

    def poll_commands(self, parameters, light):
        try:
            self._poll_commands(parameters, light)
        except Exception as exc:
            print("TELEGRAM_COMMAND_ERROR", repr(exc))

    def monitor_sensor_link(self, parameters, light):
        try:
            self._monitor_sensor_link(parameters, light)
        except Exception as exc:
            print("TELEGRAM_SENSOR_LINK_ERROR", repr(exc))

    def _monitor_sensor_link(self, parameters, light):
        config = self._config()
        if config is None:
            return

        now = time.ticks_ms()
        sensor_link = _sensor_link(light)

        if self.last_sensor_link is None:
            self.last_sensor_link = sensor_link
            if sensor_link == "sensor_waiting":
                self.sensor_wait_started_ms = now
            return

        if sensor_link != self.last_sensor_link:
            previous = self.last_sensor_link
            self.last_sensor_link = sensor_link

            if sensor_link == "sensor_waiting":
                self.sensor_wait_started_ms = now
                self.sensor_wait_notice_sent = False
                return

            if sensor_link == "sensor_lost":
                self._send(config, self._message("SENSOR LOST", parameters, light))
                return

            if sensor_link == "sensor_ok" and previous in (
                "sensor_lost",
                "sensor_waiting",
            ):
                self.sensor_wait_notice_sent = False
                self._send(config, self._message("SENSOR CONNECTED", parameters, light))
                return

        if (
            sensor_link == "sensor_waiting"
            and not self.sensor_wait_notice_sent
            and time.ticks_diff(now, self.sensor_wait_started_ms)
            >= config["sensor_wait_notice_ms"]
        ):
            if self._send(config, self._message("SENSOR WAITING", parameters, light)):
                self.sensor_wait_notice_sent = True

    def _poll_commands(self, parameters, light):
        config = self._config()
        if config is None:
            return

        if not hasattr(self, "next_update_id"):
            self.next_update_id = 0

        query = "timeout=0&limit=5"
        if self.next_update_id:
            query += "&offset=%d" % self.next_update_id

        payload = self._api_get_json(config, "getUpdates", query)
        if payload is None:
            return

        for update in payload.get("result", []):
            update_id = update.get("update_id", 0)
            if update_id >= self.next_update_id:
                self.next_update_id = update_id + 1

            message = update.get("message") or update.get("edited_message") or {}
            text = message.get("text", "").strip()
            chat = message.get("chat", {})
            chat_id = str(chat.get("id", ""))
            if not text:
                continue

            if chat_id != str(config["chat_id"]):
                print("TELEGRAM_COMMAND_IGNORED_UNAUTHORIZED")
                continue

            command = text.split()[0].split("@")[0].lower()
            if command in ("/status", "/report"):
                self._send(config, self._message("STATUS", parameters, light))
            elif command in ("/start", "/help"):
                self._send(
                    config,
                    _pre(
                        "GreenHouse commands\n"
                        "===================\n"
                        "/status - latest greenhouse report\n"
                        "/report - same as /status"
                    ),
                )

    def _update(self, parameters, light):
        config = self._config()
        if config is None:
            return

        now = time.ticks_ms()
        state = light.label
        state = _effective_state(light)
        issue_key = "%s:%s:%s" % (
            state,
            light.temperature_label,
            light.humidity_label,
        )

        if state in ("warning", "alert"):
            should_send = issue_key != self.last_issue_key
            if self.last_alert_ms is None:
                should_send = True
            elif time.ticks_diff(now, self.last_alert_ms) >= config["alert_cooldown_ms"]:
                should_send = True

            if should_send:
                title = "ALERT" if state == "alert" else "WARNING"
                if self._send(config, self._message(title, parameters, light)):
                    self.last_alert_ms = time.ticks_ms()
                    self.last_issue_key = issue_key

        elif state == "good":
            if (
                config["send_recovery"]
                and self.last_state in ("warning", "alert")
                and self.last_issue_key
            ):
                if self._send(config, self._message("RECOVERED", parameters, light)):
                    self.last_issue_key = ""

            if (
                config["report_interval_ms"] > 0
                and time.ticks_diff(now, self.last_report_ms)
                >= config["report_interval_ms"]
            ):
                if self._send(config, self._message("REPORT", parameters, light)):
                    self.last_report_ms = time.ticks_ms()

        self.last_state = state
