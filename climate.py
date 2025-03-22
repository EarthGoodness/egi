"""Climate platform for EGI VRF indoor units."""
import logging
import asyncio
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from . import const

_LOGGER = logging.getLogger(__name__)

HVAC_MODE_MAP = {
    0x01: HVACMode.COOL,
    0x02: HVACMode.DRY,
    0x04: HVACMode.FAN_ONLY,
    0x08: HVACMode.HEAT
}

FAN_MODE_MAP = {
    0x00: "auto",
    0x04: "low",
    0x02: "medium",
    0x01: "high"
}
INV_FAN_MODE_MAP = {v: k for k, v in FAN_MODE_MAP.items()}

SWING_MODE_MAP = {
    0x00: SWING_OFF,
    0x01: SWING_VERTICAL,
    0x02: SWING_HORIZONTAL,
    0x03: SWING_BOTH
}
INV_SWING_MODE_MAP = {v: k for k, v in SWING_MODE_MAP.items()}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up climate entities for each detected indoor unit."""
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    entities = [EgiVrfClimate(coord, config_entry, system, index) for (system, index) in coord.devices]
    async_add_entities(entities)

from homeassistant.helpers.update_coordinator import CoordinatorEntity

class EgiVrfClimate(CoordinatorEntity, ClimateEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.SWING_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT]

    def __init__(self, coordinator, config_entry, system, index):
        """Initialize the climate entity for an indoor unit."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._dev_key = f"{system}-{index}"
        self._client = coordinator._client
        self._system = system
        self._index = index
        entry_id = config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{system}-{index}"
        self._attr_name = f"Indoor Unit {system}-{index}"
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"{entry_id}_idu_{system}-{index}")},
            "name": self._attr_name,
            "manufacturer": "EGI",
            "model": "VRF Indoor Unit",
            "via_device": (const.DOMAIN, f"gateway_{entry_id}")
        }

    @property
    def available(self):
        data = self.coordinator.data.get(self._dev_key)
        return data.get("available", False) if data else False

    @property
    def current_temperature(self):
        return self.coordinator.data.get(self._dev_key, {}).get("current_temp")

    @property
    def target_temperature(self):
        temp = self.coordinator.data.get(self._dev_key, {}).get("target_temp")
        return temp if temp and temp > 0 else None

    @property
    def fan_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("fan_code", 0)
        return FAN_MODE_MAP.get(code, "auto")

    @property
    def swing_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("wind_code", 0)
        return SWING_MODE_MAP.get(code, SWING_OFF)

    @property
    def hvac_mode(self):
        data = self.coordinator.data.get(self._dev_key, {})
        if not data.get("power", False):
            return HVACMode.OFF
        return HVAC_MODE_MAP.get(data.get("mode_code", 0), HVACMode.FAN_ONLY)

    @property
    def hvac_action(self):
        mode = self.hvac_mode
        return {
            HVACMode.OFF: HVACAction.OFF,
            HVACMode.COOL: HVACAction.COOLING,
            HVACMode.HEAT: HVACAction.HEATING,
            HVACMode.DRY: HVACAction.DRYING,
            HVACMode.FAN_ONLY: HVACAction.FAN
        }.get(mode, HVACAction.IDLE)

    @property
    def min_temp(self):
        return 16

    @property
    def max_temp(self):
        return 30

    @property
    def extra_state_attributes(self):
        """Expose brand name and error code."""
        data = self.coordinator.data.get(self._dev_key, {})
        brand_code = self.coordinator.gateway_brand_code
        brand_name = self.coordinator.gateway_brand_name
        return {
            "brand_code": brand_code,
            "brand_name": brand_name,
            "error_code": data.get("error_code"),
            "system": self._system,
            "idu_index": self._index
        }

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        data = self.coordinator.data.get(self._dev_key, {})
        await self._async_send_command(
            data.get("power", False),
            data.get("mode_code", 0),
            int(temp),
            data.get("fan_code", const.FAN_AUTO),
            data.get("wind_code", 0x00)
        )
        _LOGGER.debug("Set temperature of %s to %s", self._dev_key, temp)

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode not in INV_FAN_MODE_MAP:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return
        code = INV_FAN_MODE_MAP[fan_mode]
        data = self.coordinator.data.get(self._dev_key, {})
        await self._async_send_command(
            data.get("power", False),
            data.get("mode_code", 0),
            data.get("target_temp", 24),
            code,
            data.get("wind_code", 0x00)
        )
        _LOGGER.debug("Set fan mode of %s to %s", self._dev_key, fan_mode)

    async def async_set_swing_mode(self, swing_mode):
        wind_code = INV_SWING_MODE_MAP.get(swing_mode, 0)
        data = self.coordinator.data.get(self._dev_key, {})
        await self._async_send_command(
            data.get("power", False),
            data.get("mode_code", 0),
            data.get("target_temp", 24),
            data.get("fan_code", const.FAN_AUTO),
            wind_code
        )
        _LOGGER.debug("Set swing mode of %s to %s", self._dev_key, swing_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        data = self.coordinator.data.get(self._dev_key, {})
        power_on = hvac_mode != HVACMode.OFF
        mode_code = {
            HVACMode.COOL: const.MODE_COOL,
            HVACMode.HEAT: const.MODE_HEAT,
            HVACMode.DRY: const.MODE_DRY,
            HVACMode.FAN_ONLY: const.MODE_FAN,
        }.get(hvac_mode, const.MODE_COOL)

        await self._async_send_command(
            power_on,
            mode_code,
            data.get("target_temp", 24),
            data.get("fan_code", const.FAN_AUTO),
            data.get("wind_code", 0x00)
        )
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
            self.coordinator.data[self._dev_key].update({
                "available": True,
                "power": power_on,
                "mode_code": mode_code,
                "target_temp": set_temp,
                "fan_code": fan_code,
                "wind_code": wind_code,
            })
            self.async_write_ha_state()
        else:
            _LOGGER.error(
                "Failed to send control command to %s (power=%s, mode=0x%02X, temp=%s, fan=0x%02X, wind=0x%02X)",
                self._dev_key, power_on, mode_code, set_temp, fan_code, wind_code
            )

        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
