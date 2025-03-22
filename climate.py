"""Climate platform for EGI VRF indoor units."""
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode, ClimateEntityFeature
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map device mode codes to Home Assistant HVAC modes
HVAC_MODE_MAP = {
    0x01: HVACMode.COOL,
    0x02: HVACMode.DRY,
    0x04: HVACMode.FAN_ONLY,
    0x08: HVACMode.HEAT,
    0x05: HVACMode.HEAT_COOL  # treat combined code (e.g., Auto) as heat_cool
}
# Map device fan speed codes to fan mode names
FAN_MODE_MAP = {
    0x00: "auto",
    0x04: "low",
    0x02: "medium",
    0x01: "high"
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entities for each detected indoor unit."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [EgiVrfClimate(coordinator, entry, uid) for uid in coordinator.units]
    async_add_entities(entities)

    # Listen for new units discovered via scanning
    async def handle_new_unit(uid, info):
        _LOGGER.debug("Adding new climate entity for unit %d", uid)
        async_add_entities([EgiVrfClimate(coordinator, entry, uid)])
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{entry.entry_id}_new_device", handle_new_unit
        )
    )

class EgiVrfClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a VRF indoor unit as a Climate entity."""
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE

    def __init__(self, coordinator, entry, unit_id: int):
        """Initialize the climate entity for a specific indoor unit."""
        super().__init__(coordinator)
        self._unit_id = unit_id
        self._entry_id = entry.entry_id
        # Unique ID and name for this entity
        self._attr_unique_id = f"{entry.entry_id}_climate_{unit_id}"
        self._attr_name = f"VRF Indoor Unit {unit_id}"
        # Determine supported HVAC modes from static info if available
        info = coordinator.unit_info.get(unit_id, {})
        supported_hvac = [HVACMode.OFF]
        modes_mask = info.get("supported_modes")
        if modes_mask:
            if modes_mask & 0x01: supported_hvac.append(HVACMode.COOL)
            if modes_mask & 0x02: supported_hvac.append(HVACMode.DRY)
            if modes_mask & 0x04: supported_hvac.append(HVACMode.FAN_ONLY)
            if modes_mask & 0x08: supported_hvac.append(HVACMode.HEAT)
            # If auto mode supported (some docs use combined bits like 0x05 or explicit bit)
            if (modes_mask & 0x10) or (modes_mask & 0x05 == 0x05):
                supported_hvac.append(HVACMode.HEAT_COOL)
        else:
            # Default assumption: supports Cool, Dry, Fan, Heat, and Auto
            supported_hvac += [HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT, HVACMode.HEAT_COOL]
        self._attr_hvac_modes = supported_hvac
        # Determine supported fan modes from static info if available
        fan_modes = []
        fan_mask = info.get("supported_fan_speeds")
        if fan_mask is not None:
            # Based on documentation example: bit0=low, bit1=medium, bit2=high, bit5=auto
            if fan_mask & 0x04: fan_modes.append("low")
            if fan_mask & 0x02: fan_modes.append("medium")
            if fan_mask & 0x01: fan_modes.append("high")
            if fan_mask & 0x20: fan_modes.append("auto")
        if not fan_modes:
            fan_modes = ["auto", "low", "medium", "high"]
        # Ensure 'auto' is first in list if present
        if "auto" in fan_modes:
            ordered = ["auto"]
            ordered += [m for m in ["low", "medium", "high"] if m in fan_modes]
            fan_modes = ordered
        self._attr_fan_modes = fan_modes
        # Temperature range
        self._attr_min_temp = float(info.get("min_temp", 16))
        self._attr_max_temp = float(info.get("max_temp", 30))

    @property
    def available(self):
        """Return True if the unit is currently present (or communication is OK)."""
        # Use coordinator's availability and check unit presence in list
        return super().available and (self._unit_id in self.coordinator.units)

    @property
    def hvac_mode(self):
        """Return current HVAC mode (including OFF)."""
        data = self.coordinator.data.get(self._unit_id)
        if not data:
            return HVACMode.OFF
        if not data.get("power", False):
            return HVACMode.OFF
        mode_val = data.get("mode")
        if mode_val is None:
            return HVACMode.OFF
        hvac = HVAC_MODE_MAP.get(mode_val)
        if hvac:
            return hvac
        # Handle any uncommon codes or combos
        if mode_val & 0x05 == 0x05:
            return HVACMode.HEAT_COOL
        if mode_val & 0x03 == 0x03:
            # Unknown combination, treat as fan mode (no heating/cooling)
            return HVACMode.FAN_ONLY
        return HVACMode.OFF

    @property
    def hvac_action(self):
        """Return current HVAC action (optional, mirror hvac_mode when on)."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return self.hvac_mode

    @property
    def current_temperature(self):
        """Return current room temperature."""
        data = self.coordinator.data.get(self._unit_id)
        if data:
            return data.get("room_temp")
        return None

    @property
    def target_temperature(self):
        """Return the target temperature (setpoint)."""
        data = self.coordinator.data.get(self._unit_id)
        if data:
            return data.get("setpoint")
        return None

    @property
    def fan_mode(self):
        """Return current fan mode."""
        data = self.coordinator.data.get(self._unit_id)
        if data:
            fan_val = data.get("fan")
            return FAN_MODE_MAP.get(fan_val, "auto")
        return "auto"

    async def async_set_hvac_mode(self, hvac_mode: str):
        """Set a new target HVAC mode (or turn on/off)."""
        base_addr = self._unit_id * 6  # base address for this unit's status registers
        if hvac_mode == HVACMode.OFF:
            # Turn off the unit (0x02 or 0x00 to power register considered off)
            await self.hass.async_add_executor_job(self.coordinator.client.write_register, base_addr, 0x02)
        else:
            # If currently off, turn on first
            curr_on = self.coordinator.data.get(self._unit_id, {}).get("power", False)
            if not curr_on:
                await self.hass.async_add_executor_job(self.coordinator.client.write_register, base_addr, 0x01)
            # Determine mode code to write
            if hvac_mode == HVACMode.COOL:
                mode_code = 0x01
            elif hvac_mode == HVACMode.DRY:
                mode_code = 0x02
            elif hvac_mode == HVACMode.FAN_ONLY:
                mode_code = 0x04
            elif hvac_mode == HVACMode.HEAT:
                mode_code = 0x08
            elif hvac_mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
                mode_code = 0x05  # use 0x05 for Auto
            else:
                _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
                return
            await self.hass.async_add_executor_job(self.coordinator.client.write_register, base_addr + 1, mode_code)
        # Refresh data
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature (setpoint)."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        value = int(round(temp))
        base_addr = self._unit_id * 6
        await self.hass.async_add_executor_job(self.coordinator.client.write_register, base_addr + 4, value)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str):
        """Set a new fan mode."""
        base_addr = self._unit_id * 6
        fan_mode_lower = fan_mode.lower()
        if fan_mode_lower == "auto":
            code = 0x00
        elif fan_mode_lower == "low":
            code = 0x04
        elif fan_mode_lower == "medium":
            code = 0x02
        elif fan_mode_lower == "high":
            code = 0x01
        else:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return
        await self.hass.async_add_executor_job(self.coordinator.client.write_register, base_addr + 3, code)
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Immediately write state (if data already available)
        self.async_write_ha_state()
