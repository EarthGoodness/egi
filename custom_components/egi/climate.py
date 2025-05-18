"""Climate platform for EGI VRF integration."""
import logging
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    adapter = data["adapter"]
    entities = [
        EgiVrfClimate(coord, adapter, config_entry, system, index)
        for (system, index) in coord.devices
    ]
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
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT
    ]

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
        return self.coordinator.data.get(self._dev_key, {}).get("current_temp")

    @property
    def target_temperature(self):
        return self.coordinator.data.get(self._dev_key, {}).get("target_temp")

    @property
    def fan_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("fan_code", 0)
        return self.adapter.decode_fan(code)

    @property
    def swing_mode(self):
        code = self.coordinator.data.get(self._dev_key, {}).get("wind_code", const.SWING_OFF)
        return "on" if code == const.SWING_ON else "off"

    @property
    def hvac_mode(self):
        data = self.coordinator.data.get(self._dev_key, {})
        if not data.get("power", False):
            return HVACMode.OFF
        return self.adapter.decode_mode(data.get("mode_code", 0))

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
        return {
            "brand_code": self.coordinator.gateway_brand_code,
            "brand_name": self.coordinator.gateway_brand_name,
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
        code = self.adapter.encode_fan(fan_mode)
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
        await self._refresh_idu_immediately()

    async def async_set_hvac_mode(self, hvac_mode):
        power_on = hvac_mode != HVACMode.OFF
        mode_code = self.adapter.encode_mode(hvac_mode)

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
