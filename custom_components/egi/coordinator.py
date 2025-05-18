"""
Coordinator for polling the EGI adapters.
"""
import logging
import time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class EgiAdapterCoordinator(DataUpdateCoordinator):
    """
    Coordinates data updates for EGI adapters using Modbus.
    """
    def __init__(
        self,
        hass,
        modbus_client,
        adapter,
        indoor_units,
        update_interval
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="egi_coordinator",
            update_interval=update_interval
        )
        self._client = modbus_client
        self._adapter = adapter
        self.devices = indoor_units
        # Initialize data: each key maps to initial availability
        self.data = {f"{sys}-{idx}": {"available": False} for sys, idx in indoor_units}

        self.gateway_brand_code = 0
        self.gateway_brand_name = "Unknown"
        self.adapter_info = {}
        self.last_update_duration = None

    async def _async_update_data(self):
        """
        Fetch updated data from the adapter, including adapter info and unit statuses.
        """
        start_time = time.perf_counter()

        # Ensure underlying client is connected
        await self.hass.async_add_executor_job(self._client.connect)

        # 1) Read adapter-level info
        try:
            info = await self.hass.async_add_executor_job(
                self._adapter.read_adapter_info,
                self._client
            )
            if isinstance(info, dict):
                self.adapter_info = info
                new_code = info.get("brand_code", 0)
                if new_code != self.gateway_brand_code:
                    self.gateway_brand_code = new_code
                    self.gateway_brand_name = self._adapter.get_brand_name(new_code)
                    _LOGGER.info(
                        "Detected adapter: brand_code=0x%02X name=%s",
                        self.gateway_brand_code, self.gateway_brand_name
                    )
            else:
                _LOGGER.warning("Adapter returned non-dict info: %s", info)
        except Exception as err:
            _LOGGER.warning("Failed to read adapter info: %s", err)
            self.gateway_brand_code = 0
            self.gateway_brand_name = "Unknown"
            self.adapter_info = {}

        # 2) Read each unit's status
        results = {}
        for system, index in self.devices:
            key = f"{system}-{index}"
            unit_start = time.perf_counter()
            try:
                status = await self.hass.async_add_executor_job(
                    self._adapter.read_status,
                    self._client,
                    system,
                    index
                )
                _LOGGER.debug(
                    "Unit %s polled in %.3f sec: %s",
                    key,
                    time.perf_counter() - unit_start,
                    status
                )
                results[key] = status
            except Exception as err:
                _LOGGER.error("Error polling unit %s: %s", key, err)
                results[key] = {"available": False}

        self.data = results

        # 3) Record duration
        duration = time.perf_counter() - start_time
        self.last_update_duration = duration
        _LOGGER.debug(
            "Update cycle completed for %d units in %.2f sec",
            len(self.devices), duration
        )

        return results
