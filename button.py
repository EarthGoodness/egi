"""Button platform for EGI VRF integration (scan trigger)."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the scan button for the EGI VRF integration."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EgiVrfScanButton(coordinator, entry)])

class EgiVrfScanButton(CoordinatorEntity, ButtonEntity):
    """Button to trigger scanning for indoor units on the VRF gateway."""

    def __init__(self, coordinator, entry):
        """Initialize the scan button entity."""
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_name = "Scan Indoor Units"
        self._attr_unique_id = f"{entry.entry_id}_scan_button"
        # Link the button to the gateway device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{entry.entry_id}")},
            "name": "EGI VRF Gateway",
            "manufacturer": "EGI",
            "model": "VRF Modbus Gateway"
        }

    async def async_press(self) -> None:
        """Handle button press to trigger a scan for IDUs."""
        _LOGGER.debug("Scan button pressed, triggering IDU scan.")
        success = await self.coordinator.async_scan_idus()
        if not success:
            _LOGGER.error("Scan for indoor units failed (communication issue).")
