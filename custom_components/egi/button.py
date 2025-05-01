"""Button platform for EGI VRF integration."""
import logging
from homeassistant.components.button import ButtonEntity
from .adapters import get_adapter

from . import const

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    buttons = [
        EgiVrfRescanButton(coordinator, config_entry, adapter),
    ]

    if getattr(adapter, "supports_brand_write", False):
        buttons.append(AdapterRestartButton(coordinator, config_entry, adapter))
        buttons.append(AdapterFactoryResetButton(coordinator, config_entry, adapter))

    async_add_entities(buttons)


class EgiVrfRescanButton(ButtonEntity):
    """Rescan Indoor Units button entity."""

    def __init__(self, coordinator, config_entry, adapter):
        """Initialize the rescan button."""
        self._coordinator = coordinator
        self._adapter = adapter
        self._entry = config_entry
        self._client = coordinator._client
        self._attr_name = "Rescan Indoor Units"
        self._attr_unique_id = f"{config_entry.entry_id}_rescan"
        entry_id = config_entry.entry_id
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "manufacturer": "EGI",
            "model": f"{self._adapter.name} - {self._coordinator.gateway_brand_name}",
        }

    async def async_press(self):
        new_found = []
        existing_set = {(sys, idx) for (sys, idx) in self._coordinator.devices}

        def _scan():
            return self._adapter.scan_devices(self._client)

        all_found = await self.hass.async_add_executor_job(_scan)
        for dev in all_found:
            if dev not in existing_set:
                new_found.append(dev)

        if new_found:
            _LOGGER.info(
                "Rescan found new indoor units: %s. Reloading integration to add them.", new_found
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
        else:
            _LOGGER.info("Rescan completed: no new indoor units found.")


class AdapterRestartButton(ButtonEntity):
    """Restart Adapter button entity."""

    def __init__(self, coordinator, config_entry, adapter):
        """Initialize the restart button."""
        self._coordinator = coordinator
        self._adapter = adapter
        self._client = coordinator._client
        self._entry = config_entry
        self._attr_name = "Restart Adapter"
        self._attr_unique_id = f"{config_entry.entry_id}_restart"
        entry_id = config_entry.entry_id
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "manufacturer": "EGI",
            "model": f"{self._adapter.name} - {self._coordinator.gateway_brand_name}",
        }

    async def async_press(self):
        _LOGGER.info("Sending adapter restart command...")
        result = await self.hass.async_add_executor_job(
            self._adapter.restart_device,
            self._client
        )
        if result:
            _LOGGER.info("Adapter restart command succeeded.")
        else:
            _LOGGER.warning("Adapter restart command failed or not supported.")


class AdapterFactoryResetButton(ButtonEntity):
    """Factory Reset Adapter button entity."""

    def __init__(self, coordinator, config_entry, adapter):
        """Initialize the factory reset button."""
        self._coordinator = coordinator
        self._adapter = adapter
        self._client = coordinator._client
        self._entry = config_entry
        self._attr_name = "Reset to Factory Defaults"
        self._attr_unique_id = f"{config_entry.entry_id}_factory_reset"
        entry_id = config_entry.entry_id
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "manufacturer": "EGI",
            "model": f"{self._adapter.name} - {self._coordinator.gateway_brand_name}",
        }

    async def async_press(self):
        _LOGGER.info("Sending factory reset command to adapter...")
        result = await self.hass.async_add_executor_job(
            self._adapter.factory_reset,
            self._client
        )
        if result:
            _LOGGER.info("Factory reset command succeeded.")
        else:
            _LOGGER.warning("Factory reset command failed or not supported.")
