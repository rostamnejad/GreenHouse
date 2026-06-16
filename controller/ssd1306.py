import time

import framebuf
from machine import Pin


SET_CONTRAST = 0x81
SET_ENTIRE_ON = 0xA4
SET_NORM_INV = 0xA6
SET_DISP = 0xAE
SET_MEM_ADDR = 0x20
SET_COL_ADDR = 0x21
SET_PAGE_ADDR = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP = 0xA0
SET_MUX_RATIO = 0xA8
SET_COM_OUT_DIR = 0xC0
SET_DISP_OFFSET = 0xD3
SET_COM_PIN_CFG = 0xDA
SET_DISP_CLK_DIV = 0xD5
SET_PRECHARGE = 0xD9
SET_VCOM_DESEL = 0xDB
SET_CHARGE_PUMP = 0x8D


class SSD1306:
    def __init__(self, width, height, external_vcc=False):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.MONO_VLSB
        )
        self.init_display()

    def init_display(self):
        for command in (
            SET_DISP | 0x00,
            SET_DISP_CLK_DIV,
            0x80,
            SET_MUX_RATIO,
            self.height - 1,
            SET_DISP_OFFSET,
            0x00,
            SET_DISP_START_LINE | 0x00,
            SET_CHARGE_PUMP,
            0x10 if self.external_vcc else 0x14,
            SET_MEM_ADDR,
            0x00,
            SET_SEG_REMAP | 0x01,
            SET_COM_OUT_DIR | 0x08,
            SET_COM_PIN_CFG,
            0x02 if self.height == 32 else 0x12,
            SET_CONTRAST,
            0x9F if self.external_vcc else 0xCF,
            SET_PRECHARGE,
            0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL,
            0x40,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_DISP | 0x01,
        ):
            self.write_cmd(command)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)

    def fill(self, color):
        self.framebuf.fill(color)

    def pixel(self, x, y, color):
        self.framebuf.pixel(x, y, color)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, text, x, y, color=1):
        self.framebuf.text(text, x, y, color)

    def hline(self, x, y, width, color):
        self.framebuf.hline(x, y, width, color)

    def vline(self, x, y, height, color):
        self.framebuf.vline(x, y, height, color)

    def line(self, x1, y1, x2, y2, color):
        self.framebuf.line(x1, y1, x2, y2, color)

    def rect(self, x, y, width, height, color):
        self.framebuf.rect(x, y, width, height, color)

    def fill_rect(self, x, y, width, height, color):
        self.framebuf.fill_rect(x, y, width, height, color)


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, external_vcc=False):
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        self.temp = bytearray(1)

        self.dc.init(Pin.OUT, value=0)
        self.res.init(Pin.OUT, value=0)
        self.cs.init(Pin.OUT, value=1)

        self.res(1)
        time.sleep_ms(1)
        self.res(0)
        time.sleep_ms(10)
        self.res(1)

        super().__init__(width, height, external_vcc)

    def write_cmd(self, command):
        self.temp[0] = command
        self.dc(0)
        self.cs(0)
        self.spi.write(self.temp)
        self.cs(1)

    def write_data(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)
