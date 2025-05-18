import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    entities = [
        RestartAdapterButton(coordinator, adapter, entry.entry_id),
        FactoryResetButton(coordinator, adapter, entry.entry_id),
        ForcePollNowButton(coordinator, entry.entry_id),
    ]

    async_add_entities(entities)

class RestartAdapterButton(ButtonEntity):
    def __init__(self, coordinator, adapter, entry_id):
        self._coordinator = coordinator
        self._adapter = adapter
        self._attr_name = "Restart Adapter"
        self._attr_unique_id = f"{entry_id}_restart_adapter"
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "name": adapter.name,
            "manufacturer": "EGI",
            "model": f"{adapter.display_type} - {adapter.get_brand_name(coordinator.gateway_brand_code)}",
        }

    async def async_press(self) -> None:
        _LOGGER.info("Restarting adapter via button entity...")
        try:
            await self.hass.async_add_executor_job(
                self._adapter.restart_adapter,
                self._coordinator._client
            )
            _LOGGER.info("Adapter restart command sent.")
        except Exception as e:
            _LOGGER.error("Failed to restart adapter: %s", e)

class FactoryResetButton(ButtonEntity):
    def __init__(self, coordinator, adapter, entry_id):
        self._adapter = adapter
        self._coordinator = coordinator
        self._attr_name = "Factory Reset Adapter"
        self._attr_unique_id = f"{entry_id}_factory_reset"
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
        }

    async def async_press(self) -> None:
        _LOGGER.info("Performing factory reset on adapter...")
        try:
            await self.hass.async_add_executor_job(
                self._adapter.factory_reset,
                self._coordinator._client
            )
            _LOGGER.info("Factory reset command sent.")
        except Exception as e:
            _LOGGER.error("Factory reset failed: %s", e)

class ForcePollNowButton(ButtonEntity):
    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._attr_name = "Force Poll Now"
        self._attr_unique_id = f"{entry_id}_force_poll"
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
        }

    async def async_press(self) -> None:
        _LOGGER.info("Manually requesting coordinator refresh...")
        try:
            await self._coordinator.async_request_refresh()
            _LOGGER.info("Poll request submitted.")
        except Exception as e:
            _LOGGER.error("Force poll failed: %s", e)