"""Coordinator for polling the EGI VRF devices."""
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from . import const
from .const import BRAND_NAMES

_LOGGER = logging.getLogger(__name__)

class EgiVrfCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, modbus_client, indoor_units):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="egi_vrf_coordinator",
            update_interval=timedelta(seconds=2)
        )
        self._client = modbus_client
        self.devices = indoor_units
        self.data = {f"{sys}-{idx}": {"available": False} for (sys, idx) in indoor_units}

        # New: global adapter brand info
        self.gateway_brand_code = 0
        self.gateway_brand_name = "Unknown"

    async def _async_update_data(self):
        """Fetch data from all indoor units and read global brand once."""
        data = {}

        # Ensure Modbus client connection runs in executor
        await self.hass.async_add_executor_job(self._client.connect)

        # Read global brand code from 0x8000 (adapter-level)
        try:
            brand_result = await self.hass.async_add_executor_job(
                self._client.read_holding_registers, 0x8000, 1
            )
            self.gateway_brand_code = brand_result[0] & 0xFF if brand_result else 0
            self.gateway_brand_name = const.BRAND_NAMES.get(
                self.gateway_brand_code,
                f"Unknown (0x{self.gateway_brand_code:02X})"
            )
            _LOGGER.info("EGI VRF Gateway brand detected: %s", self.gateway_brand_name)
        except Exception as e:
            _LOGGER.error("Failed to read VRF adapter brand: %s", e)
            self.gateway_brand_code = 0
            self.gateway_brand_name = "Unknown"


        # Loop over known IDUs and read their status
        for (system, index) in self.devices:
            key = f"{system}-{index}"
            addr = (system * 32 + index) * const.STATUS_REG_COUNT

            try:
                result = await self.hass.async_add_executor_job(
                    self._client.read_holding_registers, addr, const.STATUS_REG_COUNT
                )
            except Exception as e:
                _LOGGER.error("Exception reading status for %s: %s", key, e)
                result = None

            if result:
                power_reg, set_temp, mode_code, fan_wind_code, room_temp, error_code = result
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
