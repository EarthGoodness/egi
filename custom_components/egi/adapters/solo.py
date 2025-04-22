"""
Adapter logic for EGI HVAC Adapter Solo (single IDU).
"""

import logging
from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

BRAND_NAMES = {
    1: "Hitachi", 2: "Daikin", 3: "Toshiba", 4: "Mitsubishi Heavy",
    5: "Mitsubishi Electric", 6: "Gree", 7: "Hisense", 8: "Midea",
    9: "Haier", 10: "LG", 13: "Samsung", 15: "Panasonic", 16: "York",
    36: "Hitachi Duct", 37: "Daikin Infrared", 38: "Gree Duct 4-wire",
    39: "Gree Duct 2-wire", 40: "Midea KuFeng", 41: "Daikin MX",
    42: "Haier Duct", 43: "Hitachi Infrared", 44: "Hisense Duct",
    45: "Mitsubishi Heavy 2-wire", 46: "Haier Central", 47: "Carrier Duct",
    48: "Midea CN20", 49: "Cool Wind Coexist", 50: "Midea X1X2",
    51: "Midea Chemours", 53: "Fujitsu Duct", 54: "Ouke Duct",
    55: "AUX (2-core)", 56: "AUX (4-core)", 57: "Guangzhou York",
    58: "York Duct", 59: "Panasonic Wall HK", 88: "Simulator"
}

class AdapterSolo(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.name = "EGI HVAC Adapter Solo"
        self.max_idus = 1
        self.supports_brand_write = True

    def get_brand_name(self, code):
        return BRAND_NAMES.get(code, f"Unknown ({code})")

    def read_adapter_info(self, client):
        try:
            reg = client.read_holding_registers(2000, 1)
            if not reg:
                return {}
            return {
                "brand_code": reg[0],
                "supported_modes": 0,
                "supported_fan": 0,
                "temp_limits": 0,
                "special_info": 0,
            }
        except Exception as e:
            _LOGGER.warning("Failed to read Solo adapter info: %s", e)
            return {}

    def scan_devices(self, client):
        return [(0, 0)]

    def read_status(self, client, system, index):
        data = {
            "available": False,
            "power": False,
            "mode_code": 0,
            "target_temp": 24,
            "current_temp": 0,
            "fan_code": 0,
            "wind_code": 0,
            "error_code": 0
        }
        try:
            regs = client.read_holding_registers(0, 7)
            if not regs:
                return data
            data["available"] = True
            data["power"] = bool(regs[0])
            data["mode_code"] = regs[1] & 0xFF
            data["target_temp"] = regs[2]
            data["fan_code"] = regs[3] & 0x0F
            data["wind_code"] = regs[4] & 0xFF
            data["error_code"] = regs[5]
            data["current_temp"] = regs[6]
        except Exception as e:
            _LOGGER.error("Error reading Solo status: %s", e)
        return data

    def write_power(self, client, system, index, power_on: bool):
        return client.write_register(4000, 1 if power_on else 0)

    def write_mode(self, client, system, index, mode_code: int):
        return client.write_register(4001, mode_code & 0x0F)

    def write_temperature(self, client, system, index, temp: int):
        tval = max(16, min(30, temp))
        return client.write_register(4002, tval)

    def write_fan_speed(self, client, system, index, fan_code: int):
        return client.write_register(4003, fan_code & 0x0F)

    def write_swing(self, client, system, index, swing_code: int):
        return client.write_register(4004, swing_code & 0xFF)

    def write_brand_code(self, client, brand_id: int):
        success = client.write_register(4010, brand_id & 0xFF)
        if success:
            client.write_register(4015, 1)
        return success

    def restart_device(self, client):
        return client.write_register(4015, 1)

    def factory_reset(self, client):
        return client.write_register(4016, 1)
