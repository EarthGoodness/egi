"""
Adapter logic for EGI HVAC Adapter Solo (single IDU).
"""
import logging

from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

# Mapping of brand codes to human-readable names
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
    68: "E_ELEC", 69: "E_680NEW", 70: "E_680OLD", 71: "E_640HPU",
    72: "E_640H", 73: "E_640FC", 88: "Simulator"
}

class AdapterSolo(BaseAdapter):
    """Adapter for a single indoor unit (IDU)."""

    # Human-readable adapter name
    name = "EGI Solo Adapter"
    # Solo supports exactly one IDU
    max_idus = 1

    # Feature flags
    supports_scan = False
    supports_brand_write = True
    supports_restart = True
    supports_factory_reset = False

    @property
    def registers(self) -> list[tuple[int, str]]:
        """List of (register, description) tuples exposed by the Solo adapter."""
        return [
            (0,    "Power Status"),
            (1,    "Mode Setting"),
            (2,    "Temperature Setting"),
            (3,    "Fan Speed Setting"),
            (4,    "Louver Direction"),
            (5,    "Fault Code"),
            (6,    "Room Temperature"),
            (2000, "AC Brand"),
            (2001, "Outdoor Unit Address"),
            (2002, "Indoor Unit Address"),
            (2003, "Online Status"),
        ]

    def get_brand_name(self, code: int) -> str:
        """Return the human-readable brand name for a given code."""
        return BRAND_NAMES.get(code, f"Unknown ({code})")

    def read_adapter_info(self, client):
        """Read read-only adapter info (e.g. brand_code) from registers D2000+."""
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

    def scan_devices(self, client) -> list[tuple[int,int]]:
        """Solo has exactly one device at (0,0)."""
        return [(0, 0)]

    def read_status(self, client, system, index):
        """Read status registers D0000–D0006."""
        data = {
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
            regs = client.read_holding_registers(0, 7)
            if not regs:
                return data
            data.update({
                "available": True,
                "power": bool(regs[0]),
                "mode_code": regs[1] & 0xFF,
                "target_temp": regs[2],
                "fan_code": regs[3] & 0x0F,
                "wind_code": regs[4] & 0xFF,
                "error_code": regs[5],
                "current_temp": regs[6],
            })
        except Exception as e:
            _LOGGER.error("Error reading Solo status: %s", e)
        return data

    def write_power(self, client, system, index, power_on: bool):
        """Turn the IDU on/off via register D4000."""
        return client.write_register(4000, 1 if power_on else 0)

    def write_mode(self, client, system, index, mode_code: int):
        """Set HVAC mode via register D4001."""
        return client.write_register(4001, mode_code & 0x0F)

    def write_temperature(self, client, system, index, temp: int):
        """Set target temperature via register D4002 (16–30°C)."""
        tval = max(16, min(30, temp))
        return client.write_register(4002, tval)

    def write_fan_speed(self, client, system, index, fan_code: int):
        """Set fan speed via register D4003."""
        return client.write_register(4003, fan_code & 0x0F)

    def write_swing(self, client, system, index, swing_code: int):
        """Set louver direction via register D4004."""
        return client.write_register(4004, swing_code & 0xFF)

    def write_brand_code(self, client, brand_id: int) -> bool:
        """Select AC brand via register D4010, then trigger reboot D4015."""
        success = client.write_register(4010, brand_id & 0xFF)
        if success:
            client.write_register(4015, 1)
        return success

    def restart_device(self, client) -> bool:
        """Trigger gateway reboot via register D4015."""
        return client.write_register(4015, 1)

    def factory_reset(self, client) -> bool:
        """Factory reset via register D4016 (if supported)."""
        return client.write_register(4016, 1)
