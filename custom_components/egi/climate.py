# File: custom_components/egi/climate.py
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

# Mapping between Modbus mode codes and HA HVACMode
HVAC_MODE_MAP = {
    0x01: HVACMode.COOL,
    0x02: HVACMode.DRY,
    0x04: HVACMode.FAN_ONLY,
    0x08: HVACMode.HEAT,
}

# Fan mode mappings
FAN_MODE_MAP = {
    0x00: "auto",
    0x04: "low",
    0x02: "medium",
    0x01: "high",
}
INV_FAN_MODE_MAP = {v: k for k, v in FAN_MODE_MAP.items()}

# Swing mode mappings
SWING_MODE_MAP = {
    const.SWING_ON: SWING_ON,
    const.SWING_OFF: SWING_OFF,
}
INV_SWING_MODE_MAP = {v: k for k, v in SWING_MODE_MAP.items()}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up climate entities based on adapter type (Solo vs VRF)."""
    data = hass.data[const.DOMAIN][config_entry.entry_id]
    coord = data["coordinator"]
    adapter = data["adapter"]

    entities = []
    # Solo adapter: single climate entity
    if getattr(adapter, "max_idus", 0) == 1:
        entities.append(
            EgiVrfClimate(coord, adapter, config_entry, 1, 1)
        )
    # VRF adapters: one per discovered IDU
    else:
        for (system, index) in coord.devices:
            entities.append(
                EgiVrfClimate(coord, adapter, config_entry, system, index)
            )

    async_add_entities(entities)

class EgiVrfClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for EGI Indoor Units."""
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.SWING_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ]

    def __init__(self, coordinator, adapter, config_entry, system, index):
        super().__init__(coordinator)
        self.adapter = adapter
        self.coordinator = coordinator
        self._client = coordinator._client
        self._system = system
        self._index = index
        entry_id = config_entry.entry_id
        # Unique ID per IDU; for Solo this becomes entry_1-1
        self._attr_unique_id = f"{entry_id}_{system}-{index}"

        # Name and device_info differ for Solo vs VRF
        if getattr(adapter, "max_idus", 0) == 1:
            # Solo adapter: single device
            self._attr_name = adapter.name
            self._attr_device_info = {
                "identifiers": {(const.DOMAIN, f"adapter_{entry_id}")},
                "name": adapter.name,
                "manufacturer": "EGI",
                "model": adapter.name,
            }
        else:
            # VRF multi-unit: each IDU under gateway
            self._attr_name = f"Indoor Unit {system}-{index}"
            self._attr_device_info = {
                "identifiers": {(const.DOMAIN, f"{entry_id}_idu_{system}-{index}")},
                "name": self._attr_name,
                "manufacturer": "EGI",
                "model": "VRF Indoor Unit",
                "via_device": (const.DOMAIN, f"gateway_{entry_id}"),
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
            # coordinator.data uses keys "system-index"
            key = f"{self._system}-{self._index}"
            self.coordinator.data[key] = data
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Immediate IDU refresh failed: %s", e)

    @property
    def available(self):
        key = f"{self._system}-{self._index}"
        data = self.coordinator.data.get(key, {})
        return data.get("available", False)

    @property
    def current_temperature(self):
        key = f"{self._system}-{self._index}"
        return self.coordinator.data.get(key, {}).get("current_temp")

    @property
    def target_temperature(self):
        key = f"{self._system}-{self._index}"
        temp = self.coordinator.data.get(key, {}).get("target_temp")
        return temp if temp and temp > 0 else None

    @property
    def fan_mode(self):
        key = f"{self._system}-{self._index}"
        code = self.coordinator.data.get(key, {}).get("fan_code", 0)
        return FAN_MODE_MAP.get(code, "auto")

    @property
    def swing_mode(self):
        key = f"{self._system}-{self._index}"
        code = self.coordinator.data.get(key, {}).get("wind_code", const.SWING_OFF)
        return SWING_MODE_MAP.get(code, SWING_OFF)

    @property
    def hvac_mode(self):
        key = f"{self._system}-{self._index}"
        data = self.coordinator.data.get(key, {})
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
            HVACMode.FAN_ONLY: HVACAction.FAN,
        }.get(mode, HVACAction.IDLE)

    @property
    def min_temp(self):
        return 16

    @property
    def max_temp(self):
        return 30

    @property
    def extra_state_attributes(self):
        key = f"{self._system}-{self._index}"
        data = self.coordinator.data.get(key, {})
        return {
            "brand_code": self.coordinator.gateway_brand_code,
            "brand_name": self.coordinator.gateway_brand_name,
            "error_code": data.get("error_code"),
            "system": self._system,
            "idu_index": self._index,
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
        if swing_mode not in INV_SWING_MODE_MAP:
            _LOGGER.error("Unsupported swing mode: %s", swing_mode)
            return
        code = INV_SWING_MODE_MAP[swing_mode]
        await self.hass.async_add_executor_job(
            self.adapter.write_swing,
            self._client,
            self._system,
            self._index,
            code,
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

        # Set power
        await self.hass.async_add_executor_job(
            self.adapter.write_power,
            self._client,
            self._system,
            self._index,
            power_on,
        )
        # If turning on, also set mode
        if power_on:
            await self.hass.async_add_executor_job(
                self.adapter.write_mode,
                self._client,
                self._system,
                self._index,
                mode_code,
            )
        await self._refresh_idu_immediately()
