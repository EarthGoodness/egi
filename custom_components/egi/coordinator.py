"""Coordinator for polling the EGI VRF devices."""
import logging
import time
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
        start_time = time.perf_counter()

        await self.hass.async_add_executor_job(self._client.connect)

        try:
            adapter_info = await self.hass.async_add_executor_job(
                self._adapter.read_adapter_info, self._client
            )
            if isinstance(adapter_info, dict):
                self.adapter_info = adapter_info
                new_brand_code = adapter_info.get("brand_code", 0)
                if new_brand_code != self.gateway_brand_code:
                    self.gateway_brand_code = new_brand_code
                    self.gateway_brand_name = self._adapter.get_brand_name(new_brand_code)
                    _LOGGER.info(
                        "Detected VRF adapter: brand_code=0x%02X name=%s",
                        self.gateway_brand_code, self.gateway_brand_name
                    )
            else:
                _LOGGER.warning("Adapter returned non-dict info: %s", adapter_info)
        except Exception as e:
            _LOGGER.warning("Adapter info read failed: %s", e)
            self.gateway_brand_code = 0
            self.gateway_brand_name = "Unknown"
            self.adapter_info = {}

        for (system, index) in self.devices:
            key = f"{system}-{index}"
            idu_start = time.perf_counter()
            try:
                status = await self.hass.async_add_executor_job(
                    self._adapter.read_status, self._client, system, index
                )
                idu_time = time.perf_counter() - idu_start
                _LOGGER.debug("Polled IDU %s-%s in %.3f sec → %s", system, index, idu_time, status)
                data[key] = status
            except Exception as e:
                _LOGGER.error("Failed to update IDU (%s, %s): %s", system, index, e)
                data[key] = {"available": False}

        duration = time.perf_counter() - start_time
        _LOGGER.debug("Completed full data update for %d devices in %.2f seconds", len(self.devices), duration)

        try:
            adapter_type = self._adapter.__class__.__name__.lower().replace("adapter", "")
            self.hass.states.async_set(
                f"sensor.egi_adapter_{adapter_type}_poll_duration",
                round(duration, 2),
                {
                    "unit_of_measurement": "s",
                    "device_class": "duration",
                    "state_class": "measurement",
                    "friendly_name": f"EGI {self._adapter.display_type} Poll Time"
                }
            )
        except Exception as e:
            _LOGGER.debug("Unable to create polling duration sensor: %s", e)

        return data
