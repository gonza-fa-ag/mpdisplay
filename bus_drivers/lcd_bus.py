# SPDX-FileCopyrightText: 2023 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""
lcd_bus.py - a MicroPython library for interfacing with displays using SPI or I80

Provides similar functionality to lcd_bus from lv_binding_micropython for platforms
other than ESP32
"""

from machine import SPI, Pin
import struct


class Optional:
    pass

class _BaseBus:
    """
    Base class for bus communication. This class is meant to be subclassed by specific bus implementations.
    """
    def __init__(self) -> None:
        """
        Initialize the base bus.
        """
        self.buf1: bytearray = bytearray(1)
        self.trans_done: bool = True
        self.callback: Optional[callable] = None

    def init(
            self,
            width: int,  # Not Used
            height: int,  # Not Used
            bpp: int,  # Not Used
            buffer_size: int,
            rgb565_byte_swap: bool,
            ) -> None:
        """
        Initialize the bus with the given parameters.
        """
        self.max_transfer_sz: int = buffer_size
        self._rgb565_byte_swap: bool = rgb565_byte_swap
        if self._rgb565_byte_swap:
            print("WARNING: rgb565_byte_swap is enabled. This is VERY slow!")

    def register_callback(self, callback: callable) -> None:
        """
        Register a callback function to be called when a transaction is done.
        """
        self.callback = callback

    def bus_trans_done_cb(self) -> bool:
        """
        Callback function to be called when a transaction is done.
        """
        if self.callback is not None:
            self.callback()
        self.trans_done = True
        return False

    @staticmethod
    def rgb565_byte_swap(buf: memoryview, buf_size_px: int) -> None:
        """
        Swap the bytes in a buffer of RGB565 data.
        VERY slow!!!!!!!!!
        """
        while buf_size_px:
            buf[0], buf[1] = buf[1], buf[0]
            buf = buf[2:]
            buf_size_px -= 1

    def tx_color(self, *_, **__) -> None:
        """
        Transmit color data. Must be overridden in subclass.
        """
        raise NotImplementedError("Must be overridden in subclass")

    def tx_param(self, *_, **__) -> None:
        """
        Transmit parameters. Must be overridden in subclass.
        """
        raise NotImplementedError("Must be overridden in subclass")

    def rx_param(self, cmd: int, data: memoryview) -> int:
        """
        Receive parameters. Not yet implemented.
        """
        raise NotImplementedError("Haven't implemented rx_param yet")
    

class SPIBus(_BaseBus):
    """
    SPI bus implementation of the base bus.

    Args:
        dc (int): The pin number for the data/command pin.
        host (int, optional): The SPI host number. Defaults to 2.
        mosi (int, optional): The pin number for the MOSI pin. Defaults to -1.
        miso (int, optional): The pin number for the MISO pin. Defaults to -1.
        sclk (int, optional): The pin number for the SCLK pin. Defaults to -1.
        cs (int, optional): The pin number for the CS pin. Defaults to -1.
        freq (int, optional): The SPI clock frequency in Hz. Defaults to -1.
        tx_only (bool, optional): Whether to use transmit-only mode. Defaults to False.
        cmd_bits (int, optional): The number of bits for command transmission. Defaults to 8.
        param_bits (int, optional): The number of bits for parameter transmission. Defaults to 8.
        dc_low_on_data (bool, optional): Whether the data/command pin is low for data. Defaults to False.
        lsb_first (bool, optional): Whether to transmit LSB first. Defaults to False.
        cs_high_active (bool, optional): Whether the CS pin is active high. Defaults to False.
        spi_mode (int, optional): The SPI mode. Defaults to 0.
        wp (int, optional): The pin number for the write protect pin. Not yet supported. Defaults to -1.
        hd (int, optional): The pin number for the hold pin. Not yet supported. Defaults to -1.
        quad_spi (bool, optional): Whether to use quad SPI mode. Defaults to False.
        sio_mode (bool, optional): Whether to use SIO mode. Defaults to False.
    """
    def __init__(
            self,
            dc: int,
            host: int = 2,
            mosi: int = -1,
            miso: int = -1,
            sclk: int = -1,
            cs: int = -1,
            freq: int = -1,
            *,
            tx_only: bool = False,
            cmd_bits: int = 8,
            param_bits: int = 8,
            dc_low_on_data: bool = False,
            lsb_first: bool = False,
            cs_high_active: bool = False,
            spi_mode:int = 0,
            wp: int = -1,  # Not yet suppported
            hd: int = -1,  # Not yet supported
            quad_spi: bool = False,  # Not yet supported
            sio_mode: bool = False,  # Not yet supported
            ) -> None:
        """
        Initialize the SPI bus with the given parameters.
        """
        super().__init__()

        self._dc_cmd: bool = dc_low_on_data
        self._dc_data: bool = not dc_low_on_data

        self._cs_active: bool = cs_high_active
        self._cs_inactive: bool = not cs_high_active

        self.dc: Pin = Pin(dc, Pin.OUT, value=self._dc_cmd)
        self.cs: Pin = Pin(cs, Pin.OUT, value=self._cs_inactive) if cs != 0 else lambda val: None

        if mosi == -1 and miso == -1 and sclk == -1:
            self.spi: SPI = SPI(
                host,
                baudrate=freq,
                polarity=spi_mode & 2,
                phase=spi_mode & 1,
                bits=max(cmd_bits, param_bits),
                firstbit=SPI.LSB if lsb_first else SPI.MSB,
            )       
        else:
            self.spi: SPI = SPI(
                host,
                baudrate=freq,
                polarity=spi_mode & 2,
                phase=spi_mode & 1,
                bits=max(cmd_bits, param_bits),
                firstbit=SPI.LSB if lsb_first else SPI.MSB,
                sck=Pin(sclk, Pin.OUT),
                mosi=Pin(mosi, Pin.OUT),
                miso=Pin(miso, Pin.IN) if not tx_only else None,
            )

    def tx_color(
            self,
            cmd: int,
            data: memoryview,
            x_start: int,
            y_start: int,
            x_end: int,
            y_end: int,
            ) -> None:
        """
        Transmit color data over the SPI bus.
        """
        self.trans_done = False

        if self._rgb565_byte_swap: self.rgb565_byte_swap(data, len(data) // 2)

        # Write data in chunks of size self.max_transfer_sz (NOT WORKING YET)
        # for i in range(0, len(data), self.max_transfer_sz):
        #     chunk = data[i:i+self.max_transfer_sz]
        #     self.tx_param(cmd, chunk)

        # Write data all at once
        self.tx_param(cmd, data)
        
        self.bus_trans_done_cb()

    def tx_param(
            self,
            cmd: int,
            data: Optional[memoryview] = None,
            ) -> None:
        """
        Transmit parameters over the SPI bus.
        """
        struct.pack_into('B', self.buf1, 0, cmd)
        self.cs(self._cs_active)
        self.dc(self._dc_cmd)
        print(f"Writing {self.buf1}, {cmd}")
        self.spi.write(self.buf1)
        if len(data):
            self.dc(self._dc_data)
            self.spi.write(data)
        self.cs(self._cs_inactive)