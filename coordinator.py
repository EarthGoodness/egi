"""Coordinator for polling the EGI VRF devices."""
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import const

_LOGGER = logging.getLogger(__name__)

class EgiVrfCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, modbus_client, indoor_units):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="egi_vrf_coordinator",
            update_interval=timedelta(seconds=10)
        )
        self._client = modbus_client
        self.devices = indoor_units
        self.data = {f"{sys}-{idx}": {"available": False} for (sys, idx) in indoor_units}

    async def _async_update_data(self):
        """Fetch data from all indoor units."""
        data = {}
        # Ensure Modbus client connection runs in executor
        await self.hass.async_add_executor_job(self._client.connect)

        for (system, index) in self.devices:
            key = f"{system}-{index}"
            addr = (system * 32 + index) * const.STATUS_REG_COUNT

            result = None
            try:
                result = await self.hass.async_add_executor_job(
                    self._client.read_holding_registers, addr, const.STATUS_REG_COUNT
                )
            except Exception as e:
                _LOGGER.error("Exception reading status for %s: %s", key, e)

            if result is None:
                _LOGGER.debug("No data for indoor unit %s (marked unavailable)", key)
                data[key] = {"available": False}
                if key in self.data:
                    prev = self.data[key].copy()
                    prev["available"] = False
                    data[key] = prev
            else:
                power_reg, set_temp, mode_code, fan_wind_code, room_temp, error_code = result
                data[key] = {
                    "available": True,
                    "power": bool(power_reg),
                    "mode_code": mode_code,
                    "target_temp": set_temp,
                    "current_temp": room_temp,
                    "fan_code": fan_wind_code & 0xFF,
                    "wind_code": (fan_wind_code >> 8) & 0xFF,
                    "error_code": error_code
                }

        return data
