"""Button platform for EGI VRF integration."""
import logging
from homeassistant.components.button import ButtonEntity

from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the button entity (rescan)."""
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    # Only one button for the whole integration (gateway)
    async_add_entities([EgiVrfRescanButton(coord, config_entry)], update_before_add=False)

class EgiVrfRescanButton(ButtonEntity):
    def __init__(self, coordinator, config_entry):
        self._coordinator = coordinator
        self._client = coordinator._client
        self._entry = config_entry
        self._attr_name = "Rescan Indoor Units"
        # Unique ID for button
        self._attr_unique_id = f"{config_entry.entry_id}_rescan"
        # Device info as the hub device
        entry_id = config_entry.entry_id
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"gateway_{entry_id}")},
            "name": "EGI VRF Gateway",
            "manufacturer": "EGI",
            "model": "VRF Gateway (Modbus RTU)"
        }

    async def async_press(self):
        """Handle the button press to rescan devices."""
        new_found = []
        existing_set = { (sys, idx) for (sys, idx) in self._coordinator.devices }
        # Perform scan for all possible addresses
        def _scan():
            found = []
            for system in range(2):
                for index in range(32):
                    addr = (system * 32 + index) * const.STATUS_REG_COUNT
                    result = self._client.read_holding_registers(addr, const.STATUS_REG_COUNT)
                    if result is None:
                        continue
                    if any(val != 0 for val in result):
                        found.append((system, index))
            return found
        all_found = await self.hass.async_add_executor_job(_scan)
        for dev in all_found:
            if dev not in existing_set:
                new_found.append(dev)
        if new_found:
            _LOGGER.info("Rescan found new indoor units: %s. Reloading integration to add them.", new_found)
            # Reload config entry to initialize new devices
            await self.hass.config_entries.async_reload(self._entry.entry_id)
        else:
            _LOGGER.info("Rescan completed: no new indoor units found.")
