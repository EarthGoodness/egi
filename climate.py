"""Climate platform for EGI VRF indoor units."""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
import asyncio

from . import const

_LOGGER = logging.getLogger(__name__)

HVAC_MODE_MAP = {
    0x01: HVACMode.COOL,
    0x02: HVACMode.DRY,
    0x04: HVACMode.FAN_ONLY,
    0x08: HVACMode.HEAT
}
# Any other mode codes (0x03, 0x05, 0x06, etc.) will be treated as HVACMode.DRY or similar.

FAN_MODE_MAP = {
    0x00: "auto",
    0x04: "low",
    0x02: "medium",
    0x01: "high"
}
INV_FAN_MODE_MAP = {v: k for k, v in FAN_MODE_MAP.items()}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up climate entities for each detected indoor unit."""
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    entities = []
    for (system, index) in coord.devices:
        entities.append(EgiVrfClimate(coord, config_entry, system, index))
    async_add_entities(entities)

class EgiVrfClimate(ClimateEntity):
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT]

    def __init__(self, coordinator, config_entry, system, index):
        """Initialize the climate entity for an indoor unit."""
        self.coordinator = coordinator
        # Short device key like "0-1"
        self._dev_key = f"{system}-{index}"
        # Reference modbus client for control
        self._client = coordinator._client
        self._system = system
        self._index = index
        # Unique ID and name
        entry_id = config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{system}-{index}"
        self._attr_name = f"Indoor Unit {system}-{index}"
        # Device info for device registry
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"{entry_id}_idu_{system}-{index}")},
            "name": self._attr_name,
            "manufacturer": "EGI",
            "model": "VRF Indoor Unit",
            "via_device": (const.DOMAIN, f"gateway_{entry_id}")
        }
        # Initially assume available if present
        self._attr_available = True

    @property
    def available(self):
        """Return if the entity is available (online)."""
        data = self.coordinator.data.get(self._dev_key)
        if data:
            return data.get("available", False)
        return False

    @property
    def current_temperature(self):
        """Return current room temperature."""
        data = self.coordinator.data.get(self._dev_key)
        if data and data.get("available"):
            return data.get("current_temp")
        return None

    @property
    def target_temperature(self):
        """Return target temperature (setpoint)."""
        data = self.coordinator.data.get(self._dev_key)
        if data and data.get("available"):
            temp = data.get("target_temp")
            # Some devices might use 0 as unset, handle gracefully
            if temp is not None and temp > 0:
                return temp
        return None

    @property
    def fan_mode(self):
        """Return current fan mode."""
        data = self.coordinator.data.get(self._dev_key)
        if data and data.get("available"):
            code = data.get("fan_code", 0)
            return FAN_MODE_MAP.get(code, "auto")
        return None

    @property
    def hvac_mode(self):
        """Return current HVAC mode (heat, cool, etc.)."""
        data = self.coordinator.data.get(self._dev_key)
        if not data or not data.get("available"):
            return HVACMode.OFF
        if not data.get("power", False):
            return HVACMode.OFF
        mode_code = data.get("mode_code", 0)
        # Map mode code to HVACMode
        hvac_mode = HVAC_MODE_MAP.get(mode_code)
        if hvac_mode:
            return hvac_mode
        # If mode code is not recognized and power is on, default to closest known mode
        if mode_code and mode_code not in HVAC_MODE_MAP:
            _LOGGER.warning("Unknown mode code 0x%02X for %s, treating as DRY", mode_code, self._dev_key)
            return HVACMode.DRY
        # If mode_code is 0 and unit is on (shouldn't usually happen), treat as fan only
        return HVACMode.FAN_ONLY

    @property
    def hvac_action(self):
        """Return current operation (cooling, heating, etc.)."""
        # Derive from hvac_mode for simplicity
        mode = self.hvac_mode
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        # If we have mode as something else (shouldn't), treat as idle
        return HVACAction.IDLE

    @property
    def min_temp(self):
        # Use a safe default if device-specific not available
        return 16

    @property
    def max_temp(self):
        # Safe default
        return 30

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        # Use current state for other parameters
        data = self.coordinator.data.get(self._dev_key, {})
        is_on = data.get("power", False)
        mode_code = data.get("mode_code", 0)
        fan_code = data.get("fan_code", const.FAN_AUTO)
        wind_code = data.get("wind_code", 0x00)
        # Send command with new temperature
        await self._async_send_command(is_on, mode_code, int(temp), fan_code, wind_code)
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Set temperature of %s to %s", self._dev_key, temp)

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        # Validate mode
        if fan_mode not in INV_FAN_MODE_MAP:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return
        code = INV_FAN_MODE_MAP[fan_mode]
        data = self.coordinator.data.get(self._dev_key, {})
        is_on = data.get("power", False)
        mode_code = data.get("mode_code", 0)
        temp = data.get("target_temp", 0)
        wind_code = data.get("wind_code", 0x00)
        await self._async_send_command(is_on, mode_code, int(temp), code, wind_code)
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Set fan mode of %s to %s", self._dev_key, fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (on/off and mode type)."""
        if hvac_mode == HVACMode.OFF:
            # Turn off
            data = self.coordinator.data.get(self._dev_key, {})
            # Use last known mode or default to cool for writing, though device will turn off regardless
            last_mode_code = data.get("mode_code", 0x01)
            last_temp = data.get("target_temp", 24) or 24
            fan_code = data.get("fan_code", const.FAN_AUTO)
            wind_code = data.get("wind_code", 0x00)
            # Send off command (power off)
            await self._async_send_command(False, last_mode_code, int(last_temp), fan_code, wind_code)
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Turned off %s", self._dev_key)
        else:
            # Ensure we map the hvac_mode to a mode code
            if hvac_mode == HVACMode.COOL:
                mode_code = const.MODE_COOL
            elif hvac_mode == HVACMode.HEAT:
                mode_code = const.MODE_HEAT
            elif hvac_mode == HVACMode.DRY:
                mode_code = const.MODE_DRY
            elif hvac_mode == HVACMode.FAN_ONLY:
                mode_code = const.MODE_FAN
            else:
                _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
                return
            data = self.coordinator.data.get(self._dev_key, {})
            # If currently off, we'll turn on with given mode
            # If currently on, we're changing mode
            temp = data.get("target_temp", 24) or 24
            fan_code = data.get("fan_code", const.FAN_AUTO)
            wind_code = data.get("wind_code", 0x00)
            await self._async_send_command(True, mode_code, int(temp), fan_code, wind_code)
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Set HVAC mode of %s to %s", self._dev_key, hvac_mode)

    async def _async_send_command(self, power_on, mode_code, set_temp, fan_code, wind_code):
        base_addr = const.CONTROL_BASE_ADDR + (self._system * 32 + self._index) * const.CONTROL_REG_COUNT
        switch_val = 0x01 if power_on else 0x02
        temp_val = max(0, int(set_temp))
        mode_val = int(mode_code) & 0xFF
        fan_wind_val = (int(wind_code) << 8) | (int(fan_code) & 0xFF)
        values = [switch_val, temp_val, mode_val, fan_wind_val]
    
        success = await self.hass.async_add_executor_job(
            self._client.write_registers, base_addr, values
        )
        if success:
            # Immediately update the coordinator's cached data
            self.coordinator.data[self._dev_key].update({
                "available": True,
                "power": power_on,
                "mode_code": mode_code,
                "target_temp": set_temp,
                "fan_code": fan_code,
                "wind_code": wind_code,
            })
            # Write updated state immediately to HA frontend
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Failed to send control command to %s (power=%s, mode=0x%02X, temp=%s, fan=0x%02X, wind=0x%02X)",
                self._dev_key, power_on, mode_code, set_temp, fan_code, wind_code
            )
    
        # Trigger an async refresh in the background
        await self.coordinator.async_request_refresh()

