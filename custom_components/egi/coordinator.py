"""Coordinator for polling the EGI VRF devices."""
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class EgiVrfCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, modbus_client, adapter, indoor_units, update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="egi_coordinator",
            update_interval=update_interval
        )
        self._client = modbus_client
        self._adapter = adapter
        self.devices = indoor_units
        self.data = {f"{sys}-{idx}": {"available": False} for (sys, idx) in indoor_units}

        self.gateway_brand_code = 0
        self.gateway_brand_name = "Unknown"
        self.adapter_info = {}

    async def _async_update_data(self):
        data = {}

        await self.hass.async_add_executor_job(self._client.connect)

        try:
            adapter_info = await self.hass.async_add_executor_job(
                self._adapter.read_adapter_info, self._client
            )
            if isinstance(adapter_info, dict):
                self.adapter_info = adapter_info
                self.gateway_brand_code = adapter_info.get("brand_code", 0)
                self.gateway_brand_name = self._adapter.get_brand_name(self.gateway_brand_code)
                _LOGGER.info(
                    "Detected VRF adapter: brand_code=0x%02X name=%s",
                    self.gateway_brand_code, self.gateway_brand_name
                )
        except Exception as e:
            _LOGGER.warning("Adapter info read failed: %s", e)
            self.gateway_brand_code = 0
            self.gateway_brand_name = "Unknown"
            self.adapter_info = {}

        for (system, index) in self.devices:
            key = f"{system}-{index}"
            try:
                status = await self.hass.async_add_executor_job(
                    self._adapter.read_status, self._client, system, index
                )
                data[key] = status
            except Exception as e:
                _LOGGER.error("Failed to update IDU (%s, %s): %s", system, index, e)
                data[key] = {"available": False}

        return data
