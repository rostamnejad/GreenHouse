from machine import Pin
from neopixel import NeoPixel
from time import sleep_ms


LED_PIN_CANDIDATES = (48, 38, 21, 8, 2)
LED_COUNT = 1


def wheel(pos):
    pos = 255 - pos
    if pos < 85:
        return 255 - pos * 3, 0, pos * 3
    if pos < 170:
        pos -= 85
        return 0, pos * 3, 255 - pos * 3
    pos -= 170
    return pos * 3, 255 - pos * 3, 0


def run_on_pin(pin_number):
    led = NeoPixel(Pin(pin_number, Pin.OUT), LED_COUNT)
    print("RGB effect on GPIO", pin_number)
    for cycle in range(6):
        for step in range(256):
            led[0] = wheel((step + cycle * 24) & 255)
            led.write()
            sleep_ms(12)
    led[0] = (0, 0, 0)
    led.write()


for pin_number in LED_PIN_CANDIDATES:
    try:
        run_on_pin(pin_number)
        break
    except Exception as exc:
        print("GPIO", pin_number, "failed:", repr(exc))
