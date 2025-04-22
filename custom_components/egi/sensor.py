from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import const
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    sensors = [
        VrfGatewaySensor(coordinator, entry, adapter),
    ]

    async_add_entities(sensors)

class VrfGatewaySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, adapter):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._adapter = adapter
        self._attr_unique_id = f"{config_entry.entry_id}_gateway_info"

    @property
    def name(self):
        return f"{self.coordinator.gateway_brand_name} VRF Gateway"

    @property
    def state(self):
        return self.coordinator.gateway_brand_name

    @property
    def icon(self):
        return "mdi:hvac"

    @property
    def device_info(self):
        entry_id = self._config_entry.entry_id
        return {
            "identifiers": {(DOMAIN, f"gateway_{entry_id}")},
            "name": f"{self.coordinator.gateway_brand_name} VRF Gateway",
            "manufacturer": "EGI",
            "model": "VRF Gateway light",
            "sw_version": "1.0",
        }

    @property
    def extra_state_attributes(self):
        adapter_data = self.coordinator.adapter_info or {}
        brand_code = adapter_data.get("brand_code")
        return {
            "brand_code": brand_code,
            "brand_name": self._adapter.get_brand_name(brand_code) if brand_code is not None else "Unknown",
            "supported_modes": self._decode_bitmask(
                adapter_data.get("supported_modes", 0),
                const.SUPPORTED_MODES
            ),
            "supported_fan_speeds": self._decode_bitmask(
                adapter_data.get("supported_fan", 0),
                const.SUPPORTED_FAN_SPEEDS
            ),
            "temperature_limits": const.decode_temperature_limits(
                adapter_data.get("temp_limits", 0)
            ),
            "special_info": const.decode_special_info(
                adapter_data.get("special_info", 0)
            ),
        }

    def _decode_bitmask(self, raw_value, mapping):
        return [name for bit, name in mapping.items() if raw_value & bit]
