"""
Adapter logic for EGI VRF Adapter Pro (AC200).
Supports up to 64 IDUs, advanced registers, brand write, etc.
"""
import logging
from datetime import datetime
from .base_adapter import BaseAdapter

_LOGGER = logging.getLogger(__name__)

BRAND_NAMES = {
    1: "Hitachi VRF", 2: "Daikin VRV", 3: "Toshiba VRF", 4: "Mitsubishi Heavy VRF",
    5: "Mitsubishi Electric VRF", 6: "Gree VRF", 7: "Hisense VRF", 8: "Midea VRF",
    9: "Haier VRF", 10: "LG VRF", 13: "Samsung VRF", 14: "AUX VRF", 15: "Panasonic VRF",
    16: "York VRF", 19: "GREE 4 VRF", 21: "McQuay VRF", 24: "TCL VRF", 25: "CHIGO VRF",
    26: "TICA VRF", 35: "York T8600 VRF", 36: "COOLFAN VRF", 37: "Qingdao York VRF",
    38: "Fujitsu VRF", 39: "Samsung NotNASA VRF", 40: "Samsung NASA VRF",
    41: "Gree FG VRF", 42: "LUKO VRF", 101: "CH-Emerson VRF", 102: "CH-McQuay VRF",
    103: "Trane VRF", 104: "CH-Carrier VRF", 255: "VRF Simulator"
}

class AdapterVrfPro(BaseAdapter):
    def __init__(self):
        super().__init__()
        self._log = logging.getLogger(f"custom_components.egi.adapter.{self.__class__.__name__}")
        self.name = "EGI VRF Adapter Pro"
        self.display_type = "VRF Adapter"
        self.max_idus = 64
        self.supports_brand_write = True
        self.BRAND_NAMES = BRAND_NAMES

    def get_brand_name(self, code):
        return BRAND_NAMES.get(code, f"Unknown ({code})")

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

    def read_adapter_info(self, client):
        try:
            regs = client.read_holding_registers(15, 1)
            if not regs or len(regs) != 1:
                self._log.warning("Failed to read D0015 from adapter.")
                return {}
            raw = regs[0]
            brand_code = raw & 0xFF
            slave_id = (raw >> 8) & 0xFF
            self._log.debug("Pro adapter info: D0015=0x%04X → brand=%d, slave_id=%d", raw, brand_code, slave_id)
            return {
                "brand_code": brand_code,
                "slave_id": slave_id
            }
        except Exception as e:
            self._log.warning("Failed to read adapter info (Pro): %s", e)
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
                self._log.debug("Found IDU at 0-%d: %s", idx, regs)
            if empty_count >= 6:
                break
        self._log.info("Pro adapter scan found %d valid IDUs", len(found))
        return found

    def read_status(self, client, system, index):
        base = 24000 + index * 16
        try:
            regs = client.read_holding_registers(base, 16)
            if not regs or len(regs) != 16:
                self._log.warning("Pro adapter: No response from IDU %s-%s", system, index)
                return {"available": False}
            data = {
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
            self._log.debug("IDU %s-%s status: %s", system, index, data)
            return data
        except Exception as e:
            self._log.error("Failed reading status for Pro IDU (%s,%s): %s", system, index, e)
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
        self._log.info("Triggering host restart via D62005 = 0x0080")
        return client.write_registers(62005, [0x0080])

    def factory_reset(self, client):
        self._log.info("Triggering factory reset via D62007 = 0x0001")
        return client.write_registers(62005, [0x0040])

    def write_brand_code(self, client, brand_id: int):
        brand_word = brand_id & 0x00FF
        self._log.info("Writing brand code to D62006: 0x%04X", brand_word)
        success = client.write_registers(62006, [brand_word])
        if not success:
            self._log.warning("Failed to write brand code to D62006")
            return False
        self._log.info("Restarting adapter via D62005 = 0x0080")
        return client.write_registers(62005, [0x0080])

    def write_system_time(self, client, dt: datetime = None):
        if dt is None:
            dt = datetime.now()
        regs = [
            ((dt.year - 2000) << 8) | dt.month,
            (dt.day << 8) | dt.hour,
            (dt.minute << 8) | dt.second,
        ]
        self._log.info("Writing system time to adapter: %s → %s", dt.isoformat(), regs)
        return client.write_registers(62000, regs)
