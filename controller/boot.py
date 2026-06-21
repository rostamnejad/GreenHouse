import time
import network
from machine import Pin
from neopixel import NeoPixel
from secrets import WIFI_PASSWORD, WIFI_SSID
from version import APP_VERSION


RGB_PIN = 48
RGB_COUNT = 1
CONNECTING_COLOR = (160, 0, 0)
CONNECTED_COLOR = (0, 200, 0)


class BootLight:
    def __init__(self, pin=RGB_PIN, count=RGB_COUNT):
        try:
            self.led = NeoPixel(Pin(pin, Pin.OUT), count)
        except Exception as exc:
            self.led = None
            print("BOOT_RGB_ERROR", repr(exc))

    def show(self, color):
        if self.led is None:
            return
        self.led[0] = color
        self.led.write()

    def off(self):
        self.show((0, 0, 0))

    def blink(self, color, period_ms=300):
        if (time.ticks_ms() // period_ms) % 2 == 0:
            self.show(color)
        else:
            self.off()

    def hold(self, color, seconds):
        self.show(color)
        time.sleep(seconds)


def config_value(name, default):
    try:
        import secrets

        return getattr(secrets, name, default)
    except Exception:
        return default


def static_ip_config():
    ip = config_value("WIFI_STATIC_IP", "")
    if not ip:
        return None

    gateway = config_value("WIFI_GATEWAY", "")
    if not gateway:
        print("WiFi static IP skipped: missing WIFI_GATEWAY")
        return None

    subnet = config_value("WIFI_SUBNET_MASK", "255.255.255.0")
    dns = config_value("WIFI_DNS", gateway)
    if not dns:
        dns = gateway
    return (ip, subnet, gateway, dns)


def apply_static_ip(wlan):
    config = static_ip_config()
    if config is None:
        return

    try:
        wlan.ifconfig(config)
        print("WiFi static IP configured:", config[0])
    except Exception as exc:
        print("WiFi static IP error:", repr(exc))


def connect_wifi(light, timeout_seconds=30):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    apply_static_ip(wlan)

    if wlan.isconnected():
        return wlan

    print("WiFi connecting...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    deadline = time.ticks_add(time.ticks_ms(), timeout_seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if wlan.isconnected():
            return wlan
        light.blink(CONNECTING_COLOR)
        time.sleep_ms(100)

    return wlan


boot_light = BootLight()
wlan = connect_wifi(boot_light)
if wlan.isconnected():
    print("WiFi connected")
    print("IP:", wlan.ifconfig()[0])
    boot_light.hold(CONNECTED_COLOR, 3)
    try:
        import ota_updater

        ota_updater.check_for_updates(current_version=APP_VERSION)
    except Exception as exc:
        print("OTA_ERROR", repr(exc))
else:
    print("WiFi failed")
    print("Status:", wlan.status())
    boot_light.show(CONNECTING_COLOR)
