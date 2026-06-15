import time


DEFAULT_ALERT_COOLDOWN_SECONDS = 600
DEFAULT_REPORT_INTERVAL_SECONDS = 3600
DEFAULT_COMMAND_POLL_SECONDS = 20
REQUEST_USER_AGENT = "GreenHouse-Telegram"


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


def _value(parameters, key, empty="None"):
    value = parameters.get(key)
    if value is None:
        return empty
    return value


def _temperature_action(label):
    if label in ("too_cold", "cold"):
        return "raise temperature"
    if label in ("warm", "hot"):
        return "cool or ventilate"
    return ""


def _humidity_action(label):
    if label in ("critical_dry", "dry", "low_humidity"):
        return "raise humidity"
    if label in ("humid", "too_humid"):
        return "reduce humidity or ventilate"
    return ""


class TelegramNotifier:
    def __init__(self, controller_version):
        self.controller_version = controller_version
        self.disabled_logged = False
        self.last_alert_ms = None
        self.last_report_ms = time.ticks_ms()
        self.last_state = "waiting"
        self.last_issue_key = ""

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
            "https://api.telegram.org/bot%s/sendMessage?chat_id=%s&text=%s"
            % (config["token"], _quote(config["chat_id"]), _quote(text))
        )
        response = requests.get(url, headers={"User-Agent": REQUEST_USER_AGENT})
        try:
            status = getattr(response, "status_code", 200)
            if status == 200:
                print("TELEGRAM_SEND_OK")
                return True
            print("TELEGRAM_SEND_HTTP", status)
        finally:
            try:
                response.close()
            except Exception:
                pass
        return False

    def _message(self, title, parameters, light):
        if parameters.get("temp_c") is None and parameters.get("humidity") is None:
            return (
                "GreenHouse %s\n"
                "State: WAITING\n"
                "No sensor reading yet.\n"
                "Controller v%d"
                % (title, self.controller_version)
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

        actions = []
        temp_action = _temperature_action(light.temperature_label)
        humidity_action = _humidity_action(light.humidity_label)
        if temp_action:
            actions.append(temp_action)
        if humidity_action:
            actions.append(humidity_action)
        action_text = ", ".join(actions) if actions else "no action needed"

        sensor_version = _value(parameters, "sensor_version")
        return (
            "GreenHouse %s\n"
            "State: %s\n"
            "Temp: %.2f C (%s)\n"
            "Humidity: %.2f %% (%s)\n"
            "Pressure: %.2f mbar\n"
            "Altitude: %.1f m\n"
            "Action: %s\n"
            "Time: %s %s\n"
            "Controller v%d / Sensor v%s"
            % (
                title,
                light.label.upper(),
                _value(parameters, "temp_c", 0),
                light.temperature_label,
                _value(parameters, "humidity", 0),
                light.humidity_label,
                _value(parameters, "pressure_mbar", 0),
                _value(parameters, "altitude_m", 0),
                action_text,
                time_value,
                date_value,
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
                    "GreenHouse commands:\n/status - latest greenhouse status",
                )

    def _update(self, parameters, light):
        config = self._config()
        if config is None:
            return

        now = time.ticks_ms()
        state = light.label
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
