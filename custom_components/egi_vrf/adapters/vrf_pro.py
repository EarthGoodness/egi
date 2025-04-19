"""
Adapter logic for EGI VRF Adapter Pro (AC200).
Supports up to 64 IDUs, advanced registers, brand write, etc.
"""
import logging
from datetime import datetime
from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

BRAND_NAMES = {
    1: "Hitachi", 2: "Daikin", 3: "Toshiba", 4: "Mitsubishi Heavy",
    5: "Mitsubishi", 6: "Gree", 7: "Hisense", 8: "Midea",
    9: "Haier", 10: "LG", 13: "Samsung", 14: "AUX", 15: "Panasonic",
    16: "York", 19: "GREE4", 21: "McQuay", 24: "TCL", 25: "CHIGO",
    26: "TICA", 35: "York T8600", 36: "COOLFAN", 37: "Qingdao York",
    38: "Fujitsu", 39: "Samsung NotNASA", 40: "Samsung NASA",
    41: "Gree FG", 42: "LUKO", 101: "CH-Emerson", 102: "CH-McQuay",
    103: "Trane", 104: "CH-Carrier", 255: "Emulator"
}

class AdapterVrfPro(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.name = "EGI VRF Adapter Pro"
        self.max_idus = 64
        self.supports_brand_write = True
        self.BRAND_NAMES = BRAND_NAMES

    def get_brand_name(self, code):
        return BRAND_NAMES.get(code, f"Unknown ({code})")

    def read_adapter_info(self, client):
        try:
            # Read D0015 (address 15) — contains brand in B0–7, slave ID in B8–15
            regs = client.read_holding_registers(15, 1)
            if not regs or len(regs) != 1:
                _LOGGER.warning("Failed to read D0015 from adapter.")
                return {}
    
            raw = regs[0]
            brand_code = raw & 0xFF
            slave_id = (raw >> 8) & 0xFF
    
            _LOGGER.debug("Pro adapter info: D0015=0x%04X → brand=%d, slave_id=%d", raw, brand_code, slave_id)
    
            return {
                "brand_code": brand_code,
                "slave_id": slave_id
            }
        except Exception as e:
            _LOGGER.warning("Failed to read adapter info (Pro): %s", e)
            return {}

    def scan_devices(self, client):
        found = []
        empty_count = 0
        for idx in range(64):
            base = 24000 + idx * 16
            regs = client.read_holding_registers(base, 6)
            if not regs or len(regs) != 6:
                empty_count += 1
            elif all(val == 0x0000 for val in regs):
                empty_count += 1
            elif regs[0] > 255 or regs[1] > 255:
                empty_count += 1
            else:
                empty_count = 0
                found.append((0, idx))
            if empty_count >= 6:
                break
        _LOGGER.info("Pro adapter scan found %d valid IDUs", len(found))
        return found

    def read_status(self, client, system, index):
        base = 24000 + index * 16
        try:
            regs = client.read_holding_registers(base, 16)
            if not regs or len(regs) != 16:
                return {"available": False}
            return {
                "available": True,
                "power": bool(regs[3]),
                "target_temp": regs[4],
                "mode_code": regs[5],
                "fan_code": regs[6],
                "wind_code": regs[7],
                "current_temp": regs[10],
                "humidity": regs[11],
                "runtime_minutes": regs[13],
                "error_code": self._decode_fault_ascii(regs[14:16]),
            }
        except Exception as e:
            _LOGGER.error("Failed reading status for Pro IDU (%s,%s): %s", system, index, e)
            return {"available": False}

    def _decode_fault_ascii(self, reg_pair):
        try:
            chars = []
            for reg in reg_pair:
                chars.append(chr((reg >> 8) & 0xFF))
                chars.append(chr(reg & 0xFF))
            return "".join(c for c in chars if c.isprintable()).strip()
        except Exception:
            return ""

    def write_power(self, client, system, index, power_on: bool):
        return client.write_register(24000 + index * 16 + 3, 1 if power_on else 0)

    def write_temperature(self, client, system, index, temp: int):
        tval = max(16, min(32, temp))
        return client.write_register(24000 + index * 16 + 4, tval)

    def write_mode(self, client, system, index, mode_code: int):
        return client.write_register(24000 + index * 16 + 5, mode_code)

    def write_fan_speed(self, client, system, index, fan_code: int):
        return client.write_register(24000 + index * 16 + 6, fan_code)

    def write_swing(self, client, system, index, swing_code: int):
        return client.write_register(24000 + index * 16 + 7, swing_code)


    def restart_device(self, client):
        """Restart host via D62005 = 0x0080 (function 0x10)."""
        _LOGGER.info("Triggering host restart via D62005 = 0x0080")
        return client.write_registers(62005, [0x0080])
    
    def factory_reset(self, client):
        """Assumed factory reset via D62007 = 0x0001."""
        _LOGGER.info("Triggering factory reset via D62007 = 0x0001")
        return client.write_registers(62005, [0x0040])
    
    def write_brand_code(self, client, brand_id: int):
        """
        Write brand code (B0–7) to D62006 with B8–15 zeroed,
        then restart adapter via D62005 = 0x0080.
        """
        brand_word = brand_id & 0x00FF  # Ensure upper byte is 0
        _LOGGER.info("Writing brand code to D62006: 0x%04X", brand_word)
    
        success = client.write_registers(62006, [brand_word])
        if not success:
            _LOGGER.warning("Failed to write brand code to D62006")
            return False
    
        _LOGGER.info("Restarting adapter via D62005 = 0x0080")
        return client.write_registers(62005, [0x0080])

    def write_system_time(self, client, dt: datetime = None):
        """Write host time to D62000–D62002 using function 0x10."""
        if dt is None:
            dt = datetime.now()
    
        regs = [
            ((dt.year - 2000) << 8) | dt.month,
            (dt.day << 8) | dt.hour,
            (dt.minute << 8) | dt.second,
        ]
        _LOGGER.info("Writing system time to adapter: %s → %s", dt.isoformat(), regs)
        return client.write_registers(62000, regs)

