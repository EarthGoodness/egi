"""Modbus client wrapper for EGI VRF Gateway."""
import threading
import logging

from pymodbus.client import ModbusSerialClient, ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

class EgiModbusClient:
    def __init__(self, port=None, host=None, baudrate=9600, parity='E', stopbits=1, bytesize=8, slave_id=1, timeout=3):
        """Initialize the Modbus client for either serial or TCP connection."""
        self._slave_id = slave_id
        self._is_serial = host is None
        self._lock = threading.Lock()
        if self._is_serial:
            try:
                self._client = ModbusSerialClient(
                    port=port, 
                    baudrate=baudrate, 
                    parity=parity, 
                    stopbits=stopbits, 
                    bytesize=bytesize,
                    timeout=timeout
                )
            except Exception as e:
                _LOGGER.error("Error initializing ModbusSerialClient: %s", e)
                self._client = None
        else:
            try:
                self._client = ModbusTcpClient(host, port=port, timeout=timeout)
            except Exception as e:
                _LOGGER.error("Error initializing ModbusTcpClient: %s", e)
                self._client = None

    def connect(self):
        """Connect to the Modbus device. Returns True if successful or already connected."""
        if self._client is None:
            return False
        connected = self._client.connect()
        if not connected:
            _LOGGER.error("Failed to connect to EGI VRF Modbus gateway")
        return connected

    def close(self):
        """Close the Modbus connection."""
        try:
            if self._client:
                self._client.close()
        except Exception as e:
            _LOGGER.error("Error closing Modbus client: %s", e)

    def read_holding_registers(self, address, count=1):
        """Read holding registers. Returns list of register values or None on error."""
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return None
        with self._lock:
            try:
                result = self._client.read_holding_registers(address=address, count=count, slave=self._slave_id)
            except Exception as e:
                _LOGGER.error("Modbus read_holding_registers exception: %s", e)
                return None
            if hasattr(result, 'isError') and result.isError():
                _LOGGER.debug("Modbus read error for address %s count %s: %s", address, count, result)
                return None
            return getattr(result, 'registers', None)
    
    def write_register(self, address, value):
        """Write a single register (0x06). Returns True if successful."""
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return False
        with self._lock:
            try:
                result = self._client.write_register(address=address, value=value, slave=self._slave_id)
            except Exception as e:
                _LOGGER.error("Modbus write_register exception: %s", e)
                return False
            if hasattr(result, 'isError') and result.isError():
                _LOGGER.error("Modbus write error for address %s: %s", address, result)
                return False
            return True
    
    def write_registers(self, address, values):
        """Write multiple registers (0x10). Returns True if successful."""
        if self._client is None:
            _LOGGER.error("Modbus client is not initialized")
            return False
        with self._lock:
            try:
                result = self._client.write_registers(address=address, values=values, slave=self._slave_id)
            except Exception as e:
                _LOGGER.error("Modbus write_registers exception: %s", e)
                return False
            if hasattr(result, 'isError') and result.isError():
                _LOGGER.error("Modbus write multiple error at address %s: %s", address, result)
                return False
            return True
