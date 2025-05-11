import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import const
from .adapters import get_adapter

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    brand_names = getattr(adapter, "BRAND_NAMES", {})
    if brand_names and hasattr(adapter, "write_brand_code"):
        _LOGGER.debug("Setting up VrfBrandSelect for entry: %s", entry.entry_id)
        async_add_entities([VrfBrandSelect(coordinator, entry, adapter, brand_names)])
    else:
        _LOGGER.debug("Adapter does not support brand selection: %s", adapter.name)


class VrfBrandSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, config_entry, adapter, brand_names):
        super().__init__(coordinator)
        self._adapter = adapter
        self._client = coordinator._client
        self._entry_id = config_entry.entry_id
        self._brand_names = brand_names
        self._brand_reverse = {v: k for k, v in brand_names.items()}

        self._attr_name = "AC Brand"
        self._attr_unique_id = f"{config_entry.entry_id}_brand_select"
        self._attr_icon = "mdi:factory"
        self._attr_options = list(brand_names.values())

        entry_id = config_entry.entry_id
        brand_code = coordinator.gateway_brand_code
        brand_name = adapter.get_brand_name(brand_code)
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "name": adapter.name,
            "manufacturer": "EGI",
            "model": f"{adapter.display_type} - {brand_name}",
        }

    @property
    def current_option(self):
        code = self.coordinator.gateway_brand_code
        current = self._brand_names.get(code, f"Unknown ({code})")
        _LOGGER.debug("Current brand code: %s → %s", code, current)
        return current

    async def async_select_option(self, option):
        try:
            brand_code = self._brand_reverse.get(option)
            if brand_code is not None:
                _LOGGER.info("User selected brand: %s → code %s", option, brand_code)
                await self.hass.async_add_executor_job(
                    self._adapter.write_brand_code, self._client, brand_code
                )
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.warning("Unknown brand selection: %s", option)
        except Exception as e:
            _LOGGER.error("Brand selection failed: %s", e)
