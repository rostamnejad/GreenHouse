import time

import net_http


DEFAULT_ALERT_COOLDOWN_SECONDS = 600
DEFAULT_REPORT_INTERVAL_SECONDS = 3600
DEFAULT_COMMAND_POLL_SECONDS = 20
DEFAULT_SENSOR_WAIT_NOTICE_SECONDS = 90
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5
DEFAULT_FAILURE_BACKOFF_SECONDS = 60
REQUEST_USER_AGENT = "GreenHouse-Telegram"
PROFILE_TITLE = "گلخانه مخلوط"
PROFILE_DESCRIPTION = "آلوئه/سانسوریا + مرکبات و نخل جوان"
TEMP_SAFE_MIN_C = 18.0
TEMP_TARGET_MIN_C = 22.0
TEMP_TARGET_MAX_C = 27.0
TEMP_NOTICE_HIGH_C = 29.0
TEMP_ALERT_COLD_C = 14.0
TEMP_ALERT_HOT_C = 33.0
HUMIDITY_TARGET_MIN_PERCENT = 45.0
HUMIDITY_TARGET_MAX_PERCENT = 55.0
HUMIDITY_LOW_PERCENT = 42.0
HUMIDITY_CRITICAL_DRY_PERCENT = 35.0
HUMIDITY_NOTICE_HIGH_PERCENT = 60.0
HUMIDITY_MOLD_RISK_PERCENT = 70.0
SOIL_MIN_PERCENT = 35.0
SOIL_MAX_PERCENT = 80.0
LABEL_TEXT = {
    "waiting": "در انتظار",
    "too_cold": "خیلی سرد",
    "cold": "سرد",
    "temp_good": "مناسب",
    "warm": "گرم",
    "hot": "خیلی گرم",
    "critical_dry": "خشکی بحرانی",
    "dry": "خشک",
    "low_humidity": "رطوبت پایین",
    "humidity_good": "مناسب",
    "humid": "مرطوب",
    "too_humid": "رطوبت خیلی بالا",
    "soil_critical_dry": "خشکی بحرانی خاک",
    "soil_dry": "خاک خشک",
    "soil_good": "مناسب",
    "soil_wet": "خاک مرطوب",
    "soil_too_wet": "خاک خیلی خیس",
    "soil_disabled": "غیرفعال",
}
STATE_TEXT = {
    "good": "سالم",
    "warning": "نیاز به بررسی",
    "alert": "هشدار جدی",
    "sensor_waiting": "در انتظار سنسور",
    "sensor_lost": "ارتباط سنسور قطع است",
    "waiting": "در انتظار",
}
TITLE_TEXT = {
    "STATUS": "گلخانه - گزارش وضعیت",
    "REPORT": "گلخانه - گزارش دوره‌ای",
    "WARNING": "گلخانه - نیاز به بررسی",
    "ALERT": "گلخانه - هشدار جدی",
    "RECOVERED": "گلخانه - بازگشت به وضعیت سالم",
    "SENSOR LOST": "گلخانه - قطع ارتباط سنسور",
    "SENSOR CONNECTED": "گلخانه - وصل شدن سنسور",
    "SENSOR WAITING": "گلخانه - در انتظار سنسور",
}
SENSOR_LINK_TEXT = {
    "sensor_ok": "وصل",
    "sensor_waiting": "در انتظار داده",
    "sensor_lost": "قطع",
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
    "soil_critical_dry": "🔴",
    "soil_dry": "🟠",
    "soil_good": "🟢",
    "soil_wet": "🟠",
    "soil_too_wet": "🔴",
    "soil_disabled": "⚪",
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


def _value(parameters, key, empty="--"):
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


def _state_text(state):
    return STATE_TEXT.get(state, state)


def _title_text(title):
    return TITLE_TEXT.get(title, title)


def _state_icon(state):
    return STATE_ICON.get(state, "⚪")


def _label_icon(label):
    return LABEL_ICON.get(label, "⚪")


def _range_position(value, low, high, unit):
    if value is None:
        return "داده‌ای دریافت نشده"
    if value < low:
        return "%.2f %s پایین‌تر از حداقل" % (low - value, unit)
    if value > high:
        return "%.2f %s بالاتر از حداکثر" % (value - high, unit)
    return "در محدوده سالم"


def _temperature_position(value):
    if value is None:
        return "داده‌ای دریافت نشده"
    if value < TEMP_ALERT_COLD_C:
        return "زیر حد امن؛ سرما برای این ترکیب گیاه‌ها ریسکی است"
    if value < TEMP_SAFE_MIN_C:
        return "سردتر از بازه امن"
    if value < TEMP_TARGET_MIN_C:
        return "امن است، ولی از هدف روز کمی پایین‌تر است"
    if value <= TEMP_TARGET_MAX_C:
        return "در هدف روز"
    if value <= TEMP_NOTICE_HIGH_C:
        return "کمی بالاتر از هدف روز"
    if value <= TEMP_ALERT_HOT_C:
        return "گرم؛ تهویه و سایه ملایم را بررسی کن"
    return "خیلی گرم؛ نیاز به بررسی فوری"


def _humidity_position(value):
    if value is None:
        return "داده‌ای دریافت نشده"
    if value < HUMIDITY_CRITICAL_DRY_PERCENT:
        return "خیلی خشک"
    if value < HUMIDITY_LOW_PERCENT:
        return "خشک"
    if value < HUMIDITY_TARGET_MIN_PERCENT:
        return "کمی پایین‌تر از هدف"
    if value <= HUMIDITY_TARGET_MAX_PERCENT:
        return "در هدف مناسب"
    if value <= HUMIDITY_NOTICE_HIGH_PERCENT:
        return "کمی بالاتر از هدف؛ هنوز قابل قبول"
    if value <= HUMIDITY_MOLD_RISK_PERCENT:
        return "مرطوب؛ برای ساکولنت‌ها زیاد است"
    return "ریسک کپک و قارچ"


def _temperature_action(value):
    if value is None:
        return "منتظر خواندن دما بمان."
    if value < TEMP_ALERT_COLD_C:
        return "دما خیلی پایین است؛ گلدان‌ها را از کف و دیوار سرد دورتر کن."
    if value < TEMP_SAFE_MIN_C:
        return "دما سرد است؛ اگر می‌شود محیط را به بالای %.0f C برسان." % (
            TEMP_SAFE_MIN_C
        )
    if value < TEMP_TARGET_MIN_C:
        return "دما امن است، ولی برای رشد بهتر روزها نزدیک %.0f-%.0f C بهتر است." % (
            TEMP_TARGET_MIN_C,
            TEMP_TARGET_MAX_C,
        )
    if value > TEMP_ALERT_HOT_C:
        return "دما خیلی بالا رفته؛ تهویه، فاصله از منبع گرما و سایه ملایم را بررسی کن."
    if value > TEMP_NOTICE_HIGH_C:
        return "دما گرم است؛ اگر هوا ساکن است کمی تهویه بده."
    if value > TEMP_TARGET_MAX_C:
        return "دما کمی بالاتر از هدف است؛ فعلا پایش کافی است."
    return ""


def _humidity_action(value):
    if value is None:
        return "منتظر خواندن رطوبت بمان."
    if value < HUMIDITY_CRITICAL_DRY_PERCENT:
        return "رطوبت خیلی پایین است؛ یک ظرف آب نزدیک گلدان‌ها کمک می‌کند، خاک ساکولنت‌ها را خیس نکن."
    if value < HUMIDITY_LOW_PERCENT:
        return "رطوبت پایین است؛ برای افزایش دستی، ظرف آب نزدیک گلدان‌ها بگذار یا آبیاری سطحی نکن."
    if value < HUMIDITY_TARGET_MIN_PERCENT:
        return "رطوبت کمی پایین‌تر از هدف است؛ فقط پایش کن."
    if value > HUMIDITY_MOLD_RISK_PERCENT:
        return "رطوبت خیلی بالاست؛ تهویه کوتاه بده و آبیاری را عقب بینداز."
    if value > HUMIDITY_NOTICE_HIGH_PERCENT:
        return "رطوبت برای آلوئه و سانسوریا زیاد است؛ هوا را کمی جابه‌جا کن."
    if value > HUMIDITY_TARGET_MAX_PERCENT:
        return "رطوبت کمی بالاتر از هدف است؛ اگر شب است، تهویه ملایم بهتر است."
    return ""


def _combined_action(temp_c, humidity):
    if temp_c is None or humidity is None:
        return ""
    if temp_c < TEMP_SAFE_MIN_C and humidity > HUMIDITY_NOTICE_HIGH_PERCENT:
        return "ترکیب هوای خنک و رطوبت بالا ریسک کپک می‌دهد؛ تهویه کوتاه و توقف آبیاری بهتر است."
    if temp_c < TEMP_TARGET_MIN_C and humidity > HUMIDITY_MOLD_RISK_PERCENT:
        return "با این رطوبت بالا، دمای زیر هدف می‌تواند کپک را سریع‌تر کند؛ اول تهویه بده."
    return ""


def _soil_action(value):
    if value is None:
        return ""
    if value < SOIL_MIN_PERCENT:
        return "رطوبت خاک را حدود %.1f درصد بالا ببر." % (
            SOIL_MIN_PERCENT - value
        )
    if value > SOIL_MAX_PERCENT:
        return "آبیاری را کمتر کن؛ رطوبت خاک حدود %.1f درصد بالاتر از محدوده است." % (
            value - SOIL_MAX_PERCENT
        )
    return ""


def _required_actions(parameters):
    actions = []
    combined_action = _combined_action(
        parameters.get("temp_c"), parameters.get("humidity")
    )
    temp_action = _temperature_action(parameters.get("temp_c"))
    humidity_action = _humidity_action(parameters.get("humidity"))
    soil_action = _soil_action(parameters.get("soil_moisture"))

    for action in (combined_action, temp_action, humidity_action, soil_action):
        if action:
            actions.append(action)

    if parameters.get("temp_c") is not None and parameters.get("humidity") is not None:
        if not actions:
            return ["شرایط فعلی برای این ترکیب گیاه‌ها مناسب است.", "فعلا فقط پایش کافی است."]

    return actions if actions else ["منتظر دریافت داده از سنسور بمان."]


def _action_lines(parameters):
    lines = []
    actions = _required_actions(parameters)
    for index, action in enumerate(actions):
        icon = "🔧"
        if (
            action.startswith("شرایط")
            or action.startswith("فعلا")
            or action.startswith("وضعیت")
        ):
            icon = "✅"
        if action.startswith("منتظر"):
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


def _soil_enabled(light):
    return getattr(light, "soil_enabled", True)


class TelegramNotifier:
    def __init__(self, controller_version, status_callback=None, soil_control=None):
        self.controller_version = controller_version
        self.status_callback = status_callback
        self.soil_control = soil_control
        self.disabled_logged = False
        self.last_alert_ms = None
        self.last_report_ms = time.ticks_ms()
        self.last_state = "waiting"
        self.last_issue_key = ""
        self.last_sensor_link = None
        self.sensor_wait_started_ms = time.ticks_ms()
        self.sensor_wait_notice_sent = False
        self.network_backoff_until_ms = 0

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
            "request_timeout_s": int(
                getattr(
                    secrets,
                    "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
                    DEFAULT_REQUEST_TIMEOUT_SECONDS,
                )
            ),
            "failure_backoff_ms": int(
                getattr(
                    secrets,
                    "TELEGRAM_FAILURE_BACKOFF_SECONDS",
                    DEFAULT_FAILURE_BACKOFF_SECONDS,
                )
            )
            * 1000,
        }

    def _load_json(self, data):
        try:
            import ujson as json
        except ImportError:
            import json

        if isinstance(data, bytes):
            data = data.decode()
        return json.loads(data)

    def _in_network_backoff(self):
        return time.ticks_diff(self.network_backoff_until_ms, time.ticks_ms()) > 0

    def _start_network_backoff(self, config):
        self.network_backoff_until_ms = time.ticks_add(
            time.ticks_ms(), config["failure_backoff_ms"]
        )

    def _clear_network_backoff(self):
        self.network_backoff_until_ms = 0

    def _get(self, url, headers, timeout_seconds):
        return net_http.get(url, headers=headers, timeout=timeout_seconds)

    def _api_get_json(self, config, method, query):
        if self._in_network_backoff():
            return None

        url = "https://api.telegram.org/bot%s/%s?%s" % (
            config["token"],
            method,
            query,
        )
        try:
            response = self._get(
                url,
                {"User-Agent": REQUEST_USER_AGENT},
                config["request_timeout_s"],
            )
        except Exception as exc:
            print("TELEGRAM_HTTP_ERROR", method, repr(exc))
            self._start_network_backoff(config)
            return None

        try:
            status = getattr(response, "status_code", 200)
            data = getattr(response, "content", b"")
            if status != 200:
                print("TELEGRAM_HTTP", method, status)
                self._start_network_backoff(config)
                return None

            payload = self._load_json(data)
            if not payload.get("ok"):
                print("TELEGRAM_API_ERROR", method, payload.get("description", ""))
                self._start_network_backoff(config)
                return None

            self._clear_network_backoff()
            return payload
        finally:
            try:
                response.close()
            except Exception:
                pass

    def _send(self, config, text):
        if self._in_network_backoff():
            return False

        url = (
            "https://api.telegram.org/bot%s/sendMessage?chat_id=%s&parse_mode=HTML&text=%s"
            % (config["token"], _quote(config["chat_id"]), _quote(text))
        )
        try:
            response = self._get(
                url,
                {"User-Agent": REQUEST_USER_AGENT},
                config["request_timeout_s"],
            )
        except Exception as exc:
            print("TELEGRAM_SEND_ERROR", repr(exc))
            self._start_network_backoff(config)
            self._notify("failed")
            return False

        try:
            status = getattr(response, "status_code", 200)
            if status == 200:
                print("TELEGRAM_SEND_OK")
                self._clear_network_backoff()
                self._notify("sent")
                return True
            print("TELEGRAM_SEND_HTTP", status)
            self._start_network_backoff(config)
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
            age_text = "--" if sensor_age is None else "%d ثانیه قبل" % sensor_age
            return (
                "%s <b>%s</b>\n"
                % (state_icon, _html_escape(_title_text(title)))
            ) + _pre(
                "وضعیت      : %s\n"
                "لینک سنسور : %s\n"
                "آخرین داده : %s\n"
                "\n"
                "🔴 مشکل ارتباط سنسور\n"
                "1. 🔧 برق برد سنسور را بررسی کن.\n"
                "2. 🔧 اتصال WiFi برد سنسور را بررسی کن.\n"
                "3. 🔧 در صورت نیاز برد سنسور را ریست کن.\n"
                "\n"
                "کنترلر     : v%d"
                % (
                    _state_text(state),
                    SENSOR_LINK_TEXT.get(sensor_link, sensor_link),
                    age_text,
                    self.controller_version,
                )
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
        soil_value = parameters.get("soil_moisture")
        soil_enabled = _soil_enabled(light)
        temp_icon = _label_icon(light.temperature_label)
        humidity_icon = _label_icon(light.humidity_label)
        soil_icon = _label_icon(light.soil_label)
        temp_check = "مناسب" if light.temperature_label == "temp_good" else "بررسی"
        humidity_check = (
            "مناسب" if light.humidity_label == "humidity_good" else "بررسی"
        )
        pressure_icon = "🔵"
        if soil_enabled:
            soil_check = "مناسب" if light.soil_label == "soil_good" else "بررسی"
            soil_position = _range_position(
                soil_value, SOIL_MIN_PERCENT, SOIL_MAX_PERCENT, "%"
            )
        else:
            soil_check = "غیرفعال"
            soil_position = "سنسور خاک غیرفعال است"
        action_lines = _action_lines(parameters)

        return (
            "%s <b>%s</b>\n"
            % (state_icon, _html_escape(_title_text(title)))
        ) + _pre(
            "وضعیت      : %s\n"
            "پروفایل    : %s\n"
            "ترکیب گیاه : %s\n"
            "حالت       : پایش و راهنما؛ عملگر خودکار وصل نیست\n"
            "زمان       : %s  %s\n"
            "\n"
            "%s دما - %s\n"
            "مقدار      : %s C\n"
            "هدف روز    : %.0f-%.0f C\n"
            "وضعیت      : %s %s\n"
            "جایگاه     : %s %s\n"
            "\n"
            "%s رطوبت - %s\n"
            "مقدار      : %s %%\n"
            "هدف        : %.0f-%.0f %%\n"
            "حد توجه بالا: %.0f %%\n"
            "ریسک کپک   : %.0f %%+\n"
            "وضعیت      : %s %s\n"
            "جایگاه     : %s %s\n"
            "\n"
            "%s رطوبت خاک - %s\n"
            "مقدار      : %s %%\n"
            "محدوده سالم: %.0f-%.0f %%\n"
            "وضعیت      : %s %s\n"
            "جایگاه     : %s %s\n"
            "\n"
            "%s فشار\n"
            "مقدار      : %s mbar\n"
            "ارتفاع     : %s m\n"
            "\n"
            "🛠 راهنمای دستی\n"
            "%s\n"
            "\n"
            "نسخه‌ها\n"
            "کنترلر     : v%d\n"
            "سنسور      : v%s"
            % (
                _state_text(state),
                PROFILE_TITLE,
                PROFILE_DESCRIPTION,
                time_value,
                date_value,
                temp_icon,
                temp_check,
                _fmt(temp_value),
                TEMP_TARGET_MIN_C,
                TEMP_TARGET_MAX_C,
                temp_icon,
                _label(light.temperature_label),
                temp_icon,
                _temperature_position(temp_value),
                humidity_icon,
                humidity_check,
                _fmt(humidity_value),
                HUMIDITY_TARGET_MIN_PERCENT,
                HUMIDITY_TARGET_MAX_PERCENT,
                HUMIDITY_NOTICE_HIGH_PERCENT,
                HUMIDITY_MOLD_RISK_PERCENT,
                humidity_icon,
                _label(light.humidity_label),
                humidity_icon,
                _humidity_position(humidity_value),
                soil_icon,
                soil_check,
                _fmt(soil_value, 1),
                SOIL_MIN_PERCENT,
                SOIL_MAX_PERCENT,
                soil_icon,
                _label(light.soil_label),
                soil_icon,
                soil_position,
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
                        "دستورهای ربات گلخانه\n"
                        "====================\n"
                        "/status - دریافت آخرین گزارش و راهنمای دستی\n"
                        "/report - دریافت همان گزارش وضعیت\n"
                        "/soil - وضعیت سنسور رطوبت خاک\n"
                        "/soil_on - فعال کردن سنسور خاک نصب‌شده و کالیبره\n"
                        "/soil_off - حذف عدد خاک از گزارش و هشدار\n"
                        "حالت فعلی: پایش و راهنما؛ عملگر خودکار وصل نیست.\n"
                        "/help   - نمایش همین راهنما"
                    ),
                )
            elif command in ("/soil", "/soil_status"):
                if self.soil_control is not None:
                    self._send(config, _pre(self.soil_control(None)))
            elif command in ("/soil_on", "/soil_enable"):
                if self.soil_control is not None:
                    self._send(config, _pre(self.soil_control(True)))
            elif command in ("/soil_off", "/soil_disable"):
                if self.soil_control is not None:
                    self._send(config, _pre(self.soil_control(False)))

    def _update(self, parameters, light):
        config = self._config()
        if config is None:
            return

        now = time.ticks_ms()
        state = light.label
        state = _effective_state(light)
        issue_key = "%s:%s:%s:%s" % (
            state,
            light.temperature_label,
            light.humidity_label,
            light.soil_label,
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
