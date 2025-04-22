import logging
import asyncio
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    SWING_OFF,
    SWING_ON,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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
    const.SWING_ON: SWING_ON,
    const.SWING_OFF: SWING_OFF,
}
INV_SWING_MODE_MAP = {v: k for k, v in SWING_MODE_MAP.items()}

async def async_setup_entry(hass, config_entry, async_add_entities):
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    adapter = data["adapter"]
    entities = [EgiVrfClimate(coord, adapter, config_entry, system, index) for (system, index) in coord.devices]
    async_add_entities(entities)

class EgiVrfClimate(CoordinatorEntity, ClimateEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.SWING_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_swing_modes = ["off", "on"]
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT]

    def __init__(self, coordinator, adapter, config_entry, system, index):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.adapter = adapter
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
        
    async def _refresh_idu_immediately(self):
        """Immediately re-poll this specific IDU after a write."""
        try:
            data = await self.hass.async_add_executor_job(
                self.adapter.read_status,
                self._client,
                self._system,
                self._index,
            )
            self.coordinator.data[self._dev_key] = data
            self.async_write_ha_state()  # Update UI immediately
        except Exception as e:
            _LOGGER.error("Immediate IDU refresh failed: %s", e)

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
        code = self.coordinator.data.get(self._dev_key, {}).get("wind_code", const.SWING_ON)
        return "on" if code == const.SWING_ON else "off"

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
        await self.hass.async_add_executor_job(
            self.adapter.write_temperature,
            self._client,
            self._system,
            self._index,
            int(temp),
        )
        await self._refresh_idu_immediately()

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode not in INV_FAN_MODE_MAP:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return
        code = INV_FAN_MODE_MAP[fan_mode]
        await self.hass.async_add_executor_job(
            self.adapter.write_fan_speed,
            self._client,
            self._system,
            self._index,
            code,
        )
        await self._refresh_idu_immediately()

    async def async_set_swing_mode(self, swing_mode: str):
        wind_code = const.SWING_MODE_HA_TO_MODBUS.get(swing_mode, const.SWING_OFF)
        await self.hass.async_add_executor_job(
            self.adapter.write_swing,
            self._client,
            self._system,
            self._index,
            wind_code,
        )
        _LOGGER.debug(
            "Set swing mode of %s to %s (Modbus code: 0x%02X)",
            self._dev_key, swing_mode, wind_code
        )
        await self._refresh_idu_immediately()

    async def async_set_hvac_mode(self, hvac_mode):
        power_on = hvac_mode != HVACMode.OFF
        mode_code = {
            HVACMode.COOL: const.MODE_COOL,
            HVACMode.HEAT: const.MODE_HEAT,
            HVACMode.DRY: const.MODE_DRY,
            HVACMode.FAN_ONLY: const.MODE_FAN,
        }.get(hvac_mode, const.MODE_COOL)

        await self.hass.async_add_executor_job(
            self.adapter.write_power,
            self._client,
            self._system,
            self._index,
            power_on,
        )

        if power_on:
            await self.hass.async_add_executor_job(
                self.adapter.write_mode,
                self._client,
                self._system,
                self._index,
                mode_code,
            )

        await self._refresh_idu_immediately()