"""Sensor platform for EGI VRF integration."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors based on adapter capabilities."""
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    entities = []

    # Use adapter.registers if provided (e.g., SoloAdapter)
    registers = getattr(adapter, "registers", None)
    if registers:
        for register, description in registers:
            entities.append(
                RegisterSensor(coordinator, entry, adapter, register, description)
            )
    else:
        # Fallback for gateway-level sensors (Light/Pro)
        entities.append(VrfGatewaySensor(coordinator, entry, adapter))

    async_add_entities(entities)


class RegisterSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for a single register."""

    def __init__(self, coordinator, entry, adapter, register, description):
        super().__init__(coordinator)
        self._config_entry = entry
        self._adapter = adapter
        self._register = register
        self._attr_name = f"{adapter.name} {description}"
        self._attr_unique_id = f"{entry.entry_id}_reg_{register}"
        entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"adapter_{entry_id}")},
            "manufacturer": "EGI",
            "model": f"{adapter.name}",
        }

    @property
    def native_value(self):
        """Return current value for this register from coordinator."""
        data = getattr(self.coordinator, "data", {}) or {}
        return data.get(self._register)

    async def async_update(self):
        """Fetch register value directly from adapter."""
        try:
            result = await self.hass.async_add_executor_job(
                self._adapter.read_register,
                self._register,
            )
            self._state = result
        except Exception as err:
            _LOGGER.error("Error reading register %s: %s", self._register, err)
        self.async_write_ha_state()


class VrfGatewaySensor(CoordinatorEntity, SensorEntity):
    """Gateway-level sensor for VRF Light/Pro adapters."""

    def __init__(self, coordinator, entry, adapter):
        super().__init__(coordinator)
        self._config_entry = entry
        self._adapter = adapter
        self._attr_unique_id = f"{entry.entry_id}_gateway_info"

    @property
    def name(self):
        return f"{self._coordinator.gateway_brand_name} VRF Gateway"

    @property
    def state(self):
        return self._coordinator.gateway_brand_name

    @property
    def icon(self):
        return "mdi:hvac"

    @property
    def device_info(self):
        entry_id = self._config_entry.entry_id
        return {
            "identifiers": {(DOMAIN, f"adapter_{entry_id}")},
            "name": f"{self._coordinator.gateway_brand_name} VRF Gateway",
             "manufacturer": "EGI",
             "model": f"{self._adapter.name} - {self._coordinator.gateway_brand_name}",
             "sw_version": "1.0",
         }

    @property
    def extra_state_attributes(self):
        data = getattr(self._coordinator, "adapter_info", {}) or {}
        brand_code = data.get("brand_code")
        return {
            "brand_code": brand_code,
            "brand_name": (
                self._adapter.get_brand_name(brand_code)
                if brand_code is not None
                else "Unknown"
            ),
            "supported_modes": [
                name for bit, name in const.SUPPORTED_MODES.items()
                if data.get("supported_modes", 0) & bit
            ],
            "supported_fan_speeds": [
                name for bit, name in const.SUPPORTED_FAN_SPEEDS.items()
                if data.get("supported_fan", 0) & bit
            ],
            "temperature_limits": const.decode_temperature_limits(
                data.get("temp_limits", 0)
            ),
            "special_info": const.decode_special_info(
                data.get("special_info", 0)
            ),
        }