from machine import I2C, Pin
from time import sleep, sleep_ms, sleep_us
import time


I2C_SDA = 21
I2C_SCL = 22
I2C_MUX_ADDR = 0x70
BMP280_CHANNEL = 0
BMP280_ADDR = 0x76
SHT20_CHANNEL = 1
SHT20_ADDR = 0x40

TM1637_CLK = 27
TM1637_DIO = 26
DISPLAY_BRIGHTNESS = 4
BEEPER_PIN = 12
HUMIDITY_LOW_PERCENT = 35
HUMIDITY_CRITICAL_PERCENT = 30
LOW_ALARM_INTERVAL_SECONDS = 12
CRITICAL_ALARM_INTERVAL_SECONDS = 8
TEHRAN_OFFSET_SECONDS = 3 * 3600 + 30 * 60
TIME_SYNC_INTERVAL_SECONDS = 3600
CONTROLLER_HOST = "192.168.10.236"
CONTROLLER_PORT = 80
SEA_LEVEL_PRESSURE_MBAR = 1013.25


class TCA9548A:
    def __init__(self, i2c, addr=0x70):
        self.i2c = i2c
        self.addr = addr

    def select(self, channel):
        self.i2c.writeto(self.addr, bytes([1 << channel]))
        sleep_ms(20)

    def disable(self):
        self.i2c.writeto(self.addr, b"\x00")


class SHT20:
    def __init__(self, i2c, addr=0x40):
        self.i2c = i2c
        self.addr = addr

    def _crc8(self, data):
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x31) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    def _measure(self, command, wait_ms):
        self.i2c.writeto(self.addr, bytes([command]))
        sleep_ms(wait_ms)
        raw = self.i2c.readfrom(self.addr, 3)
        data = raw[:2]
        if raw[2] != self._crc8(data):
            raise RuntimeError("SHT20 CRC error")
        return ((data[0] << 8) | data[1]) & 0xFFFC

    def read(self):
        raw_temp = self._measure(0xF3, 100)
        temp_c = -46.85 + 175.72 * raw_temp / 65536
        raw_humidity = self._measure(0xF5, 40)
        humidity = -6 + 125 * raw_humidity / 65536
        return temp_c, humidity


class BMP280:
    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        chip_id = self.i2c.readfrom_mem(self.addr, 0xD0, 1)[0]
        if chip_id != 0x58:
            raise RuntimeError("BMP280 chip id mismatch")
        self._read_calibration()
        self.i2c.writeto_mem(self.addr, 0xF5, b"\xA0")
        self.i2c.writeto_mem(self.addr, 0xF4, b"\x27")
        sleep_ms(120)

    def _u16(self, data, offset):
        return data[offset] | (data[offset + 1] << 8)

    def _s16(self, data, offset):
        value = self._u16(data, offset)
        return value - 65536 if value > 32767 else value

    def _read_calibration(self):
        data = self.i2c.readfrom_mem(self.addr, 0x88, 24)
        self.dig_T1 = self._u16(data, 0)
        self.dig_T2 = self._s16(data, 2)
        self.dig_T3 = self._s16(data, 4)
        self.dig_P1 = self._u16(data, 6)
        self.dig_P2 = self._s16(data, 8)
        self.dig_P3 = self._s16(data, 10)
        self.dig_P4 = self._s16(data, 12)
        self.dig_P5 = self._s16(data, 14)
        self.dig_P6 = self._s16(data, 16)
        self.dig_P7 = self._s16(data, 18)
        self.dig_P8 = self._s16(data, 20)
        self.dig_P9 = self._s16(data, 22)
        self.t_fine = 0

    def read(self):
        raw = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_p = (raw[0] << 12) | (raw[1] << 4) | (raw[2] >> 4)
        adc_t = (raw[3] << 12) | (raw[4] << 4) | (raw[5] >> 4)

        var1 = (((adc_t >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (
            ((((adc_t >> 4) - self.dig_T1) * ((adc_t >> 4) - self.dig_T1)) >> 12)
            * self.dig_T3
        ) >> 14
        self.t_fine = var1 + var2
        temp_c = ((self.t_fine * 5 + 128) >> 8) / 100

        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
        if var1 == 0:
            pressure_pa = 0
        else:
            pressure = 1048576 - adc_p
            pressure = (((pressure << 31) - var2) * 3125) // var1
            var1 = (self.dig_P9 * (pressure >> 13) * (pressure >> 13)) >> 25
            var2 = (self.dig_P8 * pressure) >> 19
            pressure = ((pressure + var1 + var2) >> 8) + (self.dig_P7 << 4)
            pressure_pa = pressure / 256

        return temp_c, pressure_pa / 100


class TM1637:
    SEGMENTS = {
        " ": 0x00,
        "-": 0x40,
        "0": 0x3F,
        "1": 0x06,
        "2": 0x5B,
        "3": 0x4F,
        "4": 0x66,
        "5": 0x6D,
        "6": 0x7D,
        "7": 0x07,
        "8": 0x7F,
        "9": 0x6F,
        "A": 0x77,
        "C": 0x39,
        "E": 0x79,
        "H": 0x76,
        "L": 0x38,
        "P": 0x73,
        "R": 0x50,
        "S": 0x6D,
        "T": 0x78,
    }

    def __init__(self, clk_pin, dio_pin, brightness=4):
        self.clk = Pin(clk_pin, Pin.OUT, value=0)
        self.dio = Pin(dio_pin, Pin.OUT, value=0)
        self.brightness = max(0, min(7, brightness))
        self.show("----")

    def _delay(self):
        sleep_us(5)

    def _start(self):
        self.dio.value(1)
        self.clk.value(1)
        self._delay()
        self.dio.value(0)

    def _stop(self):
        self.clk.value(0)
        self._delay()
        self.dio.value(0)
        self._delay()
        self.clk.value(1)
        self._delay()
        self.dio.value(1)

    def _write_byte(self, value):
        for _ in range(8):
            self.clk.value(0)
            self.dio.value(value & 1)
            value >>= 1
            self._delay()
            self.clk.value(1)
            self._delay()
        self.clk.value(0)
        self.dio.init(Pin.IN)
        self._delay()
        self.clk.value(1)
        self._delay()
        self.clk.value(0)
        self.dio.init(Pin.OUT)

    def _command(self, value):
        self._start()
        self._write_byte(value)
        self._stop()

    def show(self, text):
        text = str(text)[:4]
        while len(text) < 4:
            text += " "
        self.write_segments([self.SEGMENTS.get(char.upper(), 0) for char in text])

    def write_segments(self, segments):
        self._command(0x40)
        self._start()
        self._write_byte(0xC0)
        for segment in segments:
            self._write_byte(segment)
        self._stop()
        self._command(0x88 | self.brightness)

    def show_time(self, hour, minute):
        text = "%02d%02d" % (hour, minute)
        segments = [self.SEGMENTS[char] for char in text]
        segments[1] |= 0x80
        self.write_segments(segments)

    def show_month_day(self, month, day):
        text = "%02d%02d" % (month, day)
        segments = [self.SEGMENTS[char] for char in text]
        segments[1] |= 0x80
        self.write_segments(segments)


class HumidityAlarm:
    def __init__(self, pin_number=BEEPER_PIN):
        self.beeper = Pin(pin_number, Pin.OUT, value=0)
        self.last_alarm_ms = 0
        self.beeper.value(0)

    def _pulse(self, count, on_ms, off_ms):
        for _ in range(count):
            self.beeper.value(1)
            sleep_ms(on_ms)
            self.beeper.value(0)
            sleep_ms(off_ms)

    def update(self, humidity):
        now = time.ticks_ms()

        if humidity < HUMIDITY_CRITICAL_PERCENT:
            interval_ms = CRITICAL_ALARM_INTERVAL_SECONDS * 1000
            if time.ticks_diff(now, self.last_alarm_ms) >= interval_ms:
                print("HUMIDITY_ALARM critical %.2f" % humidity)
                self._pulse(4, 55, 75)
                self.last_alarm_ms = time.ticks_ms()
        elif humidity < HUMIDITY_LOW_PERCENT:
            interval_ms = LOW_ALARM_INTERVAL_SECONDS * 1000
            if time.ticks_diff(now, self.last_alarm_ms) >= interval_ms:
                print("HUMIDITY_ALARM low %.2f" % humidity)
                self._pulse(2, 70, 120)
                self.last_alarm_ms = time.ticks_ms()
        else:
            self.beeper.value(0)


def sync_time():
    try:
        import ntptime

        ntptime.settime()
        now = local_time()
        print("TIME_SYNC_OK %02d:%02d:%02d" % (now[3], now[4], now[5]))
        return True
    except Exception as exc:
        print("TIME_SYNC_ERROR", repr(exc))
        return False


def local_time():
    return time.localtime(time.time() + TEHRAN_OFFSET_SECONDS)


def pressure_to_altitude_m(pressure_mbar):
    if pressure_mbar <= 0:
        return 0
    return 44330 * (1 - (pressure_mbar / SEA_LEVEL_PRESSURE_MBAR) ** 0.1903)


def send_parameters_to_controller(
    temp_c, humidity, pressure_mbar, altitude_m, now, jy, jm, jd
):
    sock = None
    try:
        import socket

        request = (
            "GET /parameters?temp_c=%.2f&humidity=%.2f&pressure_mbar=%.2f&altitude_m=%.1f"
            "&hour=%d&minute=%d&jy=%d&jm=%d&jd=%d HTTP/1.0\r\n"
            "Host: %s\r\n"
            "Connection: close\r\n"
            "\r\n"
        ) % (
            temp_c,
            humidity,
            pressure_mbar,
            altitude_m,
            now[3],
            now[4],
            jy,
            jm,
            jd,
            CONTROLLER_HOST,
        )

        addr = socket.getaddrinfo(CONTROLLER_HOST, CONTROLLER_PORT)[0][-1]
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect(addr)
        sock.send(request.encode())
        response = sock.recv(80)
        sock.close()
        print("CONTROLLER_SEND_OK", response.split(b"\r\n", 1)[0])
        return True
    except Exception as exc:
        print("CONTROLLER_SEND_ERROR", repr(exc))
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        return False


def gregorian_to_jalali(gy, gm, gd):
    g_days_in_month = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + g_days_in_month[gm - 1]
    )

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


def main():
    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100000)
    mux = TCA9548A(i2c, I2C_MUX_ADDR)
    display = TM1637(TM1637_CLK, TM1637_DIO, DISPLAY_BRIGHTNESS)
    alarm = HumidityAlarm(BEEPER_PIN)

    mux.select(BMP280_CHANNEL)
    pressure_sensor = BMP280(i2c, BMP280_ADDR)

    mux.select(SHT20_CHANNEL)
    sensor = SHT20(i2c, SHT20_ADDR)
    last_time_sync = 0
    if sync_time():
        last_time_sync = time.time()

    print("GreenHouse display loop started")
    while True:
        try:
            if last_time_sync == 0 or time.time() - last_time_sync >= TIME_SYNC_INTERVAL_SECONDS:
                if sync_time():
                    last_time_sync = time.time()

            mux.select(SHT20_CHANNEL)
            temp_c, humidity = sensor.read()
            alarm.update(humidity)

            mux.select(BMP280_CHANNEL)
            _, pressure_mbar = pressure_sensor.read()
            altitude_m = pressure_to_altitude_m(pressure_mbar)
            now = local_time()
            jy, jm, jd = gregorian_to_jalali(now[0], now[1], now[2])
            send_parameters_to_controller(
                temp_c, humidity, pressure_mbar, altitude_m, now, jy, jm, jd
            )
            print(
                "TIME=%02d:%02d JDATE=%04d/%02d/%02d TEMP_C=%.2f HUMIDITY=%.2f PRESSURE_MBAR=%.2f ALTITUDE_M=%.1f"
                % (now[3], now[4], jy, jm, jd, temp_c, humidity, pressure_mbar, altitude_m)
            )

            display.show_time(now[3], now[4])
            sleep(3)
            display.show_month_day(jm, jd)
            sleep(3)
            display.show("T%3d" % int(round(temp_c)))
            sleep(3)
            display.show("H%3d" % int(round(humidity)))
            sleep(3)
            pressure_value = int(round(pressure_mbar))
            if pressure_value < 1000:
                display.show("P%3d" % pressure_value)
            else:
                display.show("%4d" % pressure_value)
            sleep(3)
            display.show("ALT ")
            sleep(1)
            display.show("%4d" % int(round(altitude_m)))
            sleep(3)
        except Exception as exc:
            print("DISPLAY_LOOP_ERROR", repr(exc))
            display.show("Err ")
            sleep(2)


main()
