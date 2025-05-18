import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LOG_TARGETS = {
    "core": "custom_components.egi",
    "climate": "custom_components.egi.climate",
    "sensor": "custom_components.egi.sensor",
    "select": "custom_components.egi.select",
    "button": "custom_components.egi.button",
    "modbus": "custom_components.egi.modbus_client",
    "adapter_solo": "custom_components.egi.adapter.AdapterSolo",
    "adapter_light": "custom_components.egi.adapter.AdapterVrfLight",
    "adapter_pro": "custom_components.egi.adapter.AdapterVrfPro",
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    entities = []

    if entry.data.get("adapter_type") == "none":
        entities.extend([
            EgiLogLevelSelect(target_key, logger, entry.entry_id)
            for target_key, logger in LOG_TARGETS.items()
        ])
        _LOGGER.info("Global EGI Logging entities registered under Monitor-Only mode")
    else:
        data = hass.data[DOMAIN][entry.entry_id]
        coordinator = data["coordinator"]
        adapter = data["adapter"]
        brand_names = getattr(adapter, "BRAND_NAMES", {})
        if brand_names and hasattr(adapter, "write_brand_code"):
            _LOGGER.debug("Setting up VrfBrandSelect for entry: %s", entry.entry_id)
            entities.append(VrfBrandSelect(coordinator, entry, adapter, brand_names))

    async_add_entities(entities)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Select platform update listener triggered for entry: %s", entry.entry_id)
    # Placeholder for reacting to option updates

class EgiLogLevelSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, target_key, target_logger, entry_id):
        self._target_key = target_key
        self._target_logger = target_logger
        self._attr_name = target_key.replace('_', ' ').title()
        self._attr_unique_id = f"log_level_{target_key}"
        self._attr_options = ["debug", "info", "warning", "error"]
        self._attr_icon = "mdi:format-list-bulleted-type"
        self._attr_current_option = "info"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"log_controls_{entry_id}")},
            "name": "EGI Logging",
            "manufacturer": "EGI",
            "model": "Log Level Controls",
            "entry_type": "service"
        }

    async def async_select_option(self, option: str):
        self._attr_current_option = option
        logging.getLogger(self._target_logger).setLevel(option.upper())
        _LOGGER.info("Log level for %s set to %s", self._target_logger, option.upper())
        self.async_write_ha_state()

class VrfBrandSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "AC Brand"
    _attr_icon = "mdi:factory"

    def __init__(self, coordinator, config_entry, adapter, brand_names):
        super().__init__(coordinator)
        self._adapter = adapter
        self._client = coordinator._client
        self._entry_id = config_entry.entry_id
        self._brand_names = brand_names
        self._brand_reverse = {v: k for k, v in brand_names.items()}

        self._attr_unique_id = f"{config_entry.entry_id}_brand_select"
        self._attr_options = list(brand_names.values())

        brand_code = coordinator.gateway_brand_code
        brand_name = adapter.get_brand_name(brand_code)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"gateway_{config_entry.entry_id}")},
            name=adapter.name,
            manufacturer="EGI",
            model=f"{adapter.display_type} - {brand_name}"
        )

    @property
    def current_option(self):
        code = self.coordinator.gateway_brand_code
        return self._brand_names.get(code, f"Unknown ({code})")

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
