"""Coordinator for polling the EGI VRF devices."""
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import const
from .const import ADAPTER_INFO_ADDR, ADAPTER_INFO_REG_COUNT, OFFSET_BRAND_CODE, OFFSET_SUPPORTED_MODES, OFFSET_SUPPORTED_FAN, OFFSET_TEMP_LIMITS, OFFSET_SPECIAL_INFO, BRAND_NAMES

_LOGGER = logging.getLogger(__name__)

class EgiVrfCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, modbus_client, indoor_units, update_interval):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="egi_vrf_coordinator",
            update_interval=update_interval
        )
        self._client = modbus_client
        self.devices = indoor_units
        self.data = {f"{sys}-{idx}": {"available": False} for (sys, idx) in indoor_units}

        # New: global adapter brand info
        self.gateway_brand_code = 0
        self.gateway_brand_name = "Unknown"
        self.adapter_info = {}

    async def _async_update_data(self):
        data = {}
    
        await self.hass.async_add_executor_job(self._client.connect)
    
        # Read global adapter info explicitly
        try:
            adapter_result = await self.hass.async_add_executor_job(
                self._client.read_holding_registers, ADAPTER_INFO_ADDR, ADAPTER_INFO_REG_COUNT
            )
            if adapter_result:
                self.gateway_brand_code = adapter_result[OFFSET_BRAND_CODE] & 0xFF
                self.gateway_brand_name = BRAND_NAMES.get(
                    self.gateway_brand_code, f"Unknown (0x{self.gateway_brand_code:02X})"
                )
                self.adapter_info = {
                    "brand_code": self.gateway_brand_code,
                    "supported_modes": adapter_result[OFFSET_SUPPORTED_MODES],
                    "supported_fan": adapter_result[OFFSET_SUPPORTED_FAN],
                    "temp_limits": adapter_result[OFFSET_TEMP_LIMITS],
                    "special_info": adapter_result[OFFSET_SPECIAL_INFO],
                }
            else:
                raise ValueError("No adapter data returned")
    
            _LOGGER.info(
                "EGI VRF Gateway brand detected: %s (Code: 0x%02X)",
                self.gateway_brand_name,
                self.gateway_brand_code
            )
        except Exception as e:
            _LOGGER.error("Failed to read VRF adapter info: %s", e)
            self.gateway_brand_code = 0
            self.gateway_brand_name = "Unknown"
            self.adapter_info = {}
    
        # Loop over known IDUs and read their status explicitly
        for (system, index) in self.devices:
            key = f"{system}-{index}"
            status_addr = (system * 32 + index) * const.STATUS_REG_COUNT
            control_addr = const.CONTROL_BASE_ADDR + (system * 32 + index) * const.CONTROL_REG_COUNT
    
            try:
                status_regs = await self.hass.async_add_executor_job(
                    self._client.read_holding_registers, status_addr, const.STATUS_REG_COUNT
                )
                control_regs = await self.hass.async_add_executor_job(
                    self._client.read_holding_registers, control_addr, const.CONTROL_REG_COUNT
                )
    
            except Exception as e:
                _LOGGER.error("Exception reading registers for %s: %s", key, e)
                status_regs = None
                control_regs = None
    
            if status_regs and control_regs:
                power_reg, set_temp, mode_code, fan_wind_code, room_temp, error_code = status_regs
    
                # Decode swing modes explicitly
                control_reg = control_regs[1]
                horizontal = (control_reg >> 8) & 0x0F
                vertical = (control_reg >> 12) & 0x0F
    
                if horizontal == vertical == const.SWING_OFF:
                    swing_mode = "off"
                elif horizontal == const.SWING_ON and vertical == const.SWING_ON:
                    swing_mode = "both"
                elif vertical == const.SWING_POSITIONS["sweep"]:
                    swing_mode = "vertical"
                elif horizontal == const.SWING_POSITIONS["sweep"]:
                    swing_mode = "horizontal"
                else:
                    swing_mode = "off"
    
                data[key] = {
                    "available": True,
                    "power": bool(power_reg),
                    "mode_code": mode_code,
                    "target_temp": set_temp,
                    "current_temp": room_temp,
                    "fan_code": fan_wind_code & 0xFF,
                    "wind_code": (fan_wind_code >> 8) & 0xFF,
                    "error_code": error_code,
                }
            else:
                _LOGGER.debug("No data for indoor unit %s (marked unavailable)", key)
                data[key] = {"available": False}
                if key in self.data:
                    prev = self.data[key].copy()
                    prev["available"] = False
                    data[key] = prev
    
        return data

