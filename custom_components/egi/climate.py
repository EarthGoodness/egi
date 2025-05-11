"""Climate platform for EGI VRF integration."""
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
        brand_name = adapter.get_brand_name(coordinator.gateway_brand_code)
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, f"{entry_id}_idu_{system}-{index}")},
            "name": self._attr_name,
            "manufacturer": "EGI",
            "model": f"{brand_name} Indoor Unit",
            "via_device": (const.DOMAIN, f"gateway_{entry_id}")
        }

    async def _refresh_idu_immediately(self):
        try:
            data = await self.hass.async_add_executor_job(
                self.adapter.read_status,
                self._client,
                self._system,
                self._index,
            )
            self.coordinator.data[self._dev_key] = data
            _LOGGER.debug("Refreshed IDU %s status: %s", self._dev_key, data)
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Immediate IDU refresh failed (%s): %s", self._dev_key, e)

    @property
    def available(self):
        data = self.coordinator.data.get(self._dev_key)
        return data.get("available", False) if data else False

    @property
    def current_temperature(self):
        temp = self.coordinator.data.get(self._dev_key, {}).get("current_temp")
        _LOGGER.debug("Current temp for %s: %s", self._dev_key, temp)
        return temp

    @property
    def target_temperature(self):
        temp = self.coordinator.data.get(self._dev_key, {}).get("target_temp")
        _LOGGER.debug("Target temp for %s: %s", self._dev_key, temp)
        return temp if temp is not None else None

    @property
    def fan_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("fan_code", 0)
        mode = self.adapter.decode_fan(code)
        _LOGGER.debug("Fan mode for %s (code=%s): %s", self._dev_key, code, mode)
        return mode

    @property
    def swing_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("wind_code", const.SWING_OFF)
        mode = "on" if code == const.SWING_ON else "off"
        _LOGGER.debug("Swing mode for %s (code=%s): %s", self._dev_key, code, mode)
        return mode

    @property
    def hvac_mode(self):
        data = self.coordinator.data.get(self._dev_key, {})
        if not data.get("power", False):
            return HVACMode.OFF
        mode = self.adapter.decode_mode(data.get("mode_code", 0))
        _LOGGER.debug("HVAC mode for %s: %s", self._dev_key, mode)
        return mode

    @property
    def hvac_action(self):
        mode = self.hvac_mode
        action = {
            HVACMode.OFF: HVACAction.OFF,
            HVACMode.COOL: HVACAction.COOLING,
            HVACMode.HEAT: HVACAction.HEATING,
            HVACMode.DRY: HVACAction.DRYING,
            HVACMode.FAN_ONLY: HVACAction.FAN
        }.get(mode, HVACAction.IDLE)
        _LOGGER.debug("HVAC action for %s: %s", self._dev_key, action)
        return action

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
        _LOGGER.debug("Set temperature to %s on %s", temp, self._dev_key)
        await self.hass.async_add_executor_job(
            self.adapter.write_temperature,
            self._client,
            self._system,
            self._index,
            int(temp),
        )
        await self._refresh_idu_immediately()

    async def async_set_fan_mode(self, fan_mode):
        code = self.adapter.encode_fan(fan_mode)
        _LOGGER.debug("Set fan mode to %s (code=%s) on %s", fan_mode, code, self._dev_key)
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
        _LOGGER.debug("Set swing mode to %s (code=%s) on %s", swing_mode, wind_code, self._dev_key)
        await self.hass.async_add_executor_job(
            self.adapter.write_swing,
            self._client,
            self._system,
            self._index,
            wind_code,
        )
        await self._refresh_idu_immediately()

    async def async_set_hvac_mode(self, hvac_mode):
        power_on = hvac_mode != HVACMode.OFF
        mode_code = self.adapter.encode_mode(hvac_mode)

        _LOGGER.debug("Set HVAC mode to %s (code=%s) with power=%s on %s", hvac_mode, mode_code, power_on, self._dev_key)
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
