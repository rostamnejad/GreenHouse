import time
import network
from secrets import WIFI_PASSWORD, WIFI_SSID
from version import APP_VERSION


def connect_wifi(timeout_seconds=30):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan

    print("WiFi connecting...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    for _ in range(timeout_seconds):
        if wlan.isconnected():
            return wlan
        time.sleep(1)

    return wlan


wlan = connect_wifi()
if wlan.isconnected():
    print("WiFi connected")
    print("IP:", wlan.ifconfig()[0])
    try:
        import ota_updater

        ota_updater.check_for_updates(current_version=APP_VERSION)
    except Exception as exc:
        print("OTA_ERROR", repr(exc))
else:
    print("WiFi failed")
    print("Status:", wlan.status())
