import time
import network
from secrets import WIFI_SSID, WIFI_PASSWORD

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

if not wlan.isconnected():
    print("WiFi connecting...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(30):
        if wlan.isconnected():
            break
        time.sleep(1)

if wlan.isconnected():
    print("WiFi connected")
    print("IP:", wlan.ifconfig()[0])
    try:
        import ota_updater

        ota_updater.check_for_updates()
    except Exception as exc:
        print("OTA_ERROR", repr(exc))
else:
    print("WiFi failed")
    print("Status:", wlan.status())
