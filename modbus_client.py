"""Module for Modbus communication with EGI VRF Gateway."""
import logging
from pymodbus.client import ModbusSerialClient

from .const import (
    DEFAULT_BAUDRATE, DEFAULT_PARITY, DEFAULT_STOPBITS, DEFAULT_SLAVE_ID,
    MAX_IDU_UNITS, BASE_BRAND_ADDR, BRAND_REG_STRIDE, STATUS_REG_COUNT
)

_LOGGER = logging.getLogger(__name__)

class EgiVrfModbusClient:
    """Modbus RTU client for EGI VRF Gateway."""

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 parity: str = DEFAULT_PARITY, stopbits: int = DEFAULT_STOPBITS,
                 slave_id: int = DEFAULT_SLAVE_ID):
        """Initialize and open serial connection."""
        self._port = port
        self._baudrate = baudrate
        # parity should be 'N', 'E', or 'O'
        self._parity = parity.upper() if parity else 'N'
        self._stopbits = stopbits
        self._slave_id = slave_id
        self._client = None
        # Attempt to connect on init
        try:
            self._client = ModbusSerialClient(
                port=self._port,
                baudrate=self._baudrate,
                parity=self._parity,
                stopbits=self._stopbits,
                bytesize=8,
                timeout=3
            )
        except Exception as exc:
            _LOGGER.error("Failed to initialize Modbus client: %s", exc)
            self._client = None
        else:
            if not self._client.connect():
                _LOGGER.error("Unable to open Modbus serial port %s", self._port)
                # Keep client object; actual reads will handle reconnection if possible.

    def close(self):
        """Close the serial connection."""
        if self._client:
            try:
                self._client.close()
            except Exception as exc:
                _LOGGER.warning("Error closing Modbus connection: %s", exc)
        self._client = None

    def _ensure_connected(self) -> bool:
        """Ensure the connection is open. Try to reconnect if not."""
        if self._client is None:
            try:
                self._client = ModbusSerialClient(
                    port=self._port,
                    baudrate=self._baudrate,
                    parity=self._parity,
                    stopbits=self._stopbits,
                    bytesize=8,
                    timeout=3
                )
            except Exception as exc:
                _LOGGER.error("Failed to reinitialize Modbus client: %s", exc)
                return False
        if not self._client.connect():
            _LOGGER.error("Modbus client not connected (port %s)", self._port)
            return False
        return True

    def read_holding_registers(self, address: int, count: int = 1):
        """Read holding registers starting at address."""
        if not self._ensure_connected():
            return None
        try:
            result = self._client.read_holding_registers(address=address, count=count, slave=self._slave_id)
        except Exception as exc:
            _LOGGER.error("Modbus read_holding_registers failed at 0x%04X: %s", address, exc)
            return None
        if result is None or result.isError():
            _LOGGER.error("Modbus error reading 0x%04X (count %d): %s", address, count, result)
            return None
        return result.registers

    def write_register(self, address: int, value: int):
        """Write a single holding register."""
        if not self._ensure_connected():
            return False
        try:
            result = self._client.write_register(address, value, slave=self._slave_id)
        except Exception as exc:
            _LOGGER.error("Modbus write_register failed at 0x%04X: %s", address, exc)
            return False
        if result is None or result.isError():
            _LOGGER.error("Modbus error writing 0x%04X = %s: %s", address, value, result)
            return False
        return True

    def scan_idus(self):
        """Scan for indoor units by reading brand registers. Returns dict of {idu_index: info} for each detected IDU."""
        found = {}
        for idx in range(MAX_IDU_UNITS):
            addr = BASE_BRAND_ADDR + BRAND_REG_STRIDE * idx
            reg = self.read_holding_registers(address=addr, count=1)
            if reg is None:
                _LOGGER.error("Scanning aborted at IDU %d due to communication error.", idx)
                return None  # communication failure, abort and indicate failure
            brand_code = reg[0] & 0xFF  # brand code is 1 byte (low byte)
            if brand_code != 0:
                info = {"brand_code": brand_code}
                # Read the rest of performance registers for this IDU
                perf_regs = self.read_holding_registers(address=addr + 1, count=BRAND_REG_STRIDE - 1)
                if perf_regs is None:
                    _LOGGER.warning("Could not read performance registers for IDU %d", idx)
                    perf_regs = [0] * (BRAND_REG_STRIDE - 1)
                # D8001: supported modes (2 bytes), D8002: supported wind speeds (1 byte),
                # D8003: temp range (2 bytes), D8004: special features (1 byte).
                if len(perf_regs) >= 1:
                    supported_modes_word = perf_regs[0]
                    info["supported_modes"] = supported_modes_word
                if len(perf_regs) >= 2:
                    supported_fan_byte = perf_regs[1] & 0xFF
                    info["supported_fan_speeds"] = supported_fan_byte
                if len(perf_regs) >= 3:
                    temp_range_word = perf_regs[2]
                    max_temp = (temp_range_word >> 8) & 0xFF
                    min_temp = temp_range_word & 0xFF
                    if min_temp > max_temp:
                        min_temp, max_temp = max_temp, min_temp
                    info["min_temp"] = min_temp
                    info["max_temp"] = max_temp
                if len(perf_regs) >= 4:
                    special_byte = perf_regs[3] & 0xFF
                    info["special_flags"] = special_byte
                found[idx] = info
        return found