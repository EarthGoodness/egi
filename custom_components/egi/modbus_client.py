"""Modbus client wrapper for EGI VRF Gateway with safe shared connection handling."""

import threading
import logging
from pymodbus.client import ModbusSerialClient, ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

# Global pool for shared Modbus clients by connection key
_client_pool = {}

def get_shared_client(connection_type, slave_id=1, **kwargs):
    """Create or reuse a shared Modbus client based on unique connection key."""
    key = _get_client_key(connection_type, **kwargs)

    if key not in _client_pool:
        if connection_type == "serial":
            port = kwargs.get("port")
            _LOGGER.info("Creating new ModbusSerialClient for port: %s", port)
            client = ModbusSerialClient(
                port=port,
                baudrate=kwargs.get("baudrate", 9600),
                parity=kwargs.get("parity", "E"),
                stopbits=kwargs.get("stopbits", 1),
                bytesize=kwargs.get("bytesize", 8),
                timeout=3,
            )
        else:
            _LOGGER.info("Creating new ModbusTcpClient for host: %s", kwargs.get("host"))
            client = ModbusTcpClient(
                host=kwargs.get("host"),
                port=kwargs.get("port", 502),
                timeout=3,
            )

        connected = client.connect()
        if connected:
            _LOGGER.info("Modbus client connected successfully: %s", key)
        else:
            _LOGGER.warning("Modbus client failed to connect: %s", key)

        _client_pool[key] = client
    else:
        _LOGGER.debug("Reusing existing Modbus client for key: %s", key)

    return EgiModbusClient(_client_pool[key], slave_id=slave_id)

def _get_client_key(connection_type, **kwargs):
    """Generate unique key for each client based on port or host."""
    if connection_type == "serial":
        port = kwargs.get("port", "").strip()
        return f"serial::{port}"
    else:
        host = kwargs.get("host", "").strip()
        port = kwargs.get("port", 502)
        return f"tcp::{host}:{port}"

class EgiModbusClient:
    """Wraps pymodbus client and applies slave ID + thread lock. Shared client safety."""

    def __init__(self, modbus_client, slave_id=1):
        self._client = modbus_client
        self._slave_id = slave_id
        self._lock = threading.Lock()

    def connect(self):
        """Never re-connect a shared client."""
        _LOGGER.debug("connect() skipped — using pre-connected shared client.")
        return True

    def close(self):
        """Never close a shared client."""
        _LOGGER.debug("close() skipped — shared client remains open.")
        pass

    def read_holding_registers(self, address, count=1):
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return None
        with self._lock:
            try:
                result = self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self._slave_id
                )
            except Exception as e:
                _LOGGER.error("Modbus read_holding_registers exception: %s", e)
                return None
            if hasattr(result, "isError") and result.isError():
                _LOGGER.warning("Modbus read error at addr=%s count=%s: %s", address, count, result)
                return None
            return getattr(result, "registers", None)

    def write_register(self, address, value):
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return False
        with self._lock:
            try:
                result = self._client.write_register(
                    address=address,
                    value=value,
                    slave=self._slave_id
                )
            except Exception as e:
                _LOGGER.error("Modbus write_register exception: %s", e)
                return False
            if hasattr(result, "isError") and result.isError():
                _LOGGER.warning("Modbus write error at addr=%s: %s", address, result)
                return False
            return True

    def write_registers(self, address, values):
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return False
        with self._lock:
            try:
                result = self._client.write_registers(
                    address=address,
                    values=values,
                    slave=self._slave_id
                )
            except Exception as e:
                _LOGGER.error("Modbus write_registers exception: %s", e)
                return False
            if hasattr(result, "isError") and result.isError():
                _LOGGER.warning("Modbus write multiple error at addr=%s: %s", address, result)
                return False
            return True
