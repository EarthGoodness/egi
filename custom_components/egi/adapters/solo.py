"""
Adapter logic for EGI HVAC Adapter Solo (single IDU).
"""
import logging
from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

BRAND_NAMES = {
    1: "Hitachi VRF (2-wire)", 2: "Daikin VRF (2-wire)", 3: "Toshiba VRF (2-wire)",
    4: "Mitsubishi Heavy Industries VRF (2-wire)", 5: "Mitsubishi Electric VRF (4-wire)",
    6: "Gree VRF (2-wire)", 7: "Hisense VRF (2-wire)", 9: "Haier VRF (3-wire)",
    10: "LG", 13: "Samsung", 15: "Panasonic VRF (2-wire)", 16: "York VRF (2-wire)",
    18: "Toshiba Ducted (4-wire)", 19: "Panasonic Ducted (4-wire)",
    20: "Midea W1/W2 (2-wire)", 36: "Hitachi Ducted (4-wire)", 37: "Daikin IR (2-wire)",
    38: "Gree Ducted (4-wire)", 39: "Gree Ducted (2-wire)", 40: "Coolwind VRF (4-wire)",
    41: "Daikin MX Ducted (4-wire)", 42: "Haier Ducted (3-wire)", 43: "Hitachi IR (2-wire)",
    44: "Hisense Ducted (4-wire)", 45: "Mitsubishi Heavy VRF (3-wire)",
    46: "Haier REMOTE terminal", 47: "Carrier Ducted (4-wire)", 48: "Midea CN20 (4-wire)",
    49: "Coolwind Coexistence (bidirectional)", 50: "Midea X1/X2 (2-wire)",
    51: "Midea Comet (2-wire)", 53: "Fujitsu Ducted (3-wire)", 54: "Ouko Ducted (4-wire)",
    55: "AUX VRF (2-wire)", 56: "AUX Ducted (4-wire)", 57: "Guangzhou York VRF (4-wire)",
    58: "York Ducted (4-wire)", 59: "Panasonic Wall-mounted (HK, 4-wire)",
    68: "Electra Central HVAC", 69: "Tadiran Central HVAC (TAC680 New)", 70: "Tadiran Central HVAC (TAC680 Old)", 71: "Tadiran Central HVAC (TAC640HPU)",
    72: "Tadiran Central HVAC (TAC640H)", 73: "Tadiran Central HVAC (TAC640FC)", 88: "HVAC Simulator"
}


class AdapterSolo(BaseAdapter):
    BRAND_NAMES = BRAND_NAMES

    def __init__(self):
        super().__init__()
        self.name = "EGI HVAC Adapter Solo"              # → For device_info["name"]
        self.display_type = "Solo Adapter"               # → For device_info["model"]
        self.max_idus = 1
        self.supports_scan = False
        self.supports_brand_write = True
        self.supports_factory_reset = False
        self.supports_restart = True

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

    def decode_mode(self, value):
        return {
            0x01: "heat",
            0x02: "cool",
            0x04: "fan_only",
            0x08: "dry",
        }.get(value, "fan_only")

    def encode_mode(self, ha_mode):
        return {
            "heat": 0x01,
            "cool": 0x02,
            "fan_only": 0x04,
            "dry": 0x08,
        }.get(ha_mode, 0x02)

    def decode_fan(self, value):
        return {
            0x00: "auto",
            0x01: "low",
            0x02: "medium",
            0x03: "high",
        }.get(value, "auto")

    def encode_fan(self, ha_fan):
        return {
            "auto": 0x00,
            "low": 0x01,
            "medium": 0x02,
            "high": 0x03,
        }.get(ha_fan, 0x00)
