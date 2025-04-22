"""
Adapter logic for the standard EGI VRF Adapter Light (up to 32 IDUs).
Uses registers and approach from the existing integration's code.
"""
import logging
from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

ADAPTER_INFO_ADDR = 8000
ADAPTER_INFO_REG_COUNT = 5

STATUS_REG_COUNT = 6
CONTROL_BASE_ADDR = 4000
CONTROL_REG_COUNT = 4

BRAND_NAMES = {
    0x01: "Hitachi",
    0x02: "Daikin",
    0x03: "Toshiba",
    0x04: "Mitsubishi Heavy",
    0x05: "Mitsubishi",
    0x06: "Gree",
    0x07: "Hisense",
    0x08: "Midea",
    0x09: "Haier",
    0x0A: "LG",
    0x0D: "Samsung",
    0x0E: "AUX",
    0x0F: "Panasonic",
    0x10: "York",
    0x15: "McQuay",
    0x18: "TCL",
    0x1A: "Tianjia",
    0x23: "York Water",
    0x24: "Cool Wind",
    0x25: "Qingdao York",
    0x26: "Fujitsu",
    0x65: "Emerson Water",
    0x66: "McQuay Water",
    0x7E: "Toshiba",
    0xFF: "Simulator",
}

class AdapterVrfLight(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.name = "EGI VRF Adapter Light"
        self.max_idus = 32
        self.supports_brand_write = False

    def get_brand_name(self, code):
        return BRAND_NAMES.get(code, f"Unknown (0x{code:02X})")

    def read_adapter_info(self, client):
        try:
            regs = client.read_holding_registers(ADAPTER_INFO_ADDR, ADAPTER_INFO_REG_COUNT)
            if not regs:
                return {}

            return {
                "brand_code": regs[0] & 0xFF,
                "supported_modes": regs[1],
                "supported_fan": regs[2],
                "temp_limits": regs[3],
                "special_info": regs[4],
            }
        except Exception as e:
            _LOGGER.warning("Failed to read adapter info for VRF Light: %s", e)
            return {}

    def scan_devices(self, client):
        found = []
        for system in range(4):
            for index in range(32):
                addr = (system * 32 + index) * STATUS_REG_COUNT
                result = client.read_holding_registers(addr, STATUS_REG_COUNT)
                if result and any(val != 0 for val in result):
                    found.append((system, index))
        return found

    def read_status(self, client, system, index):
        key_data = {
            "available": False,
            "power": False,
            "mode_code": 0,
            "target_temp": 24,
            "current_temp": 0,
            "fan_code": 0,
            "wind_code": 0,
            "error_code": 0,
        }
        try:
            status_addr = (system * 32 + index) * STATUS_REG_COUNT
            control_addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT

            status_regs = client.read_holding_registers(status_addr, STATUS_REG_COUNT)
            control_regs = client.read_holding_registers(control_addr, CONTROL_REG_COUNT)
            if not status_regs or not control_regs:
                return key_data

            power_reg, set_temp, mode_code, fan_wind_code, room_temp, error_code = status_regs

            key_data["available"] = True
            key_data["power"] = bool(power_reg)
            key_data["mode_code"] = mode_code & 0xFF
            key_data["target_temp"] = set_temp
            key_data["current_temp"] = room_temp
            key_data["fan_code"] = fan_wind_code & 0xFF
            key_data["wind_code"] = (fan_wind_code >> 8) & 0xFF
            key_data["error_code"] = error_code

        except Exception as e:
            _LOGGER.error("Error reading status for system %s index %s: %s", system, index, e)

        return key_data

    def write_power(self, client, system, index, power_on: bool):
        base_addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT
        return client.write_register(base_addr, 0x01 if power_on else 0x02)

    def write_mode(self, client, system, index, mode_code: int):
        addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT + 2
        return client.write_register(addr, mode_code & 0xFF)

    def write_temperature(self, client, system, index, temp: int):
        addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT + 1
        return client.write_register(addr, max(16, min(30, temp)))

    def write_fan_speed(self, client, system, index, fan_code: int):
        base_addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT + 3
        regs = client.read_holding_registers(base_addr, 1)
        if not regs:
            return False
        wind = (regs[0] >> 8) & 0xFF
        return client.write_register(base_addr, (wind << 8) | (fan_code & 0xFF))

    def write_swing(self, client, system, index, swing_code: int):
        base_addr = CONTROL_BASE_ADDR + (system * 32 + index) * CONTROL_REG_COUNT + 3
        regs = client.read_holding_registers(base_addr, 1)
        if not regs:
            return False
        fan = regs[0] & 0xFF
        return client.write_register(base_addr, ((swing_code & 0xFF) << 8) | fan)
