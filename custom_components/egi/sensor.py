"""Sensor platform for EGI VRF integration."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors based on adapter type."""
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    adapter = data["adapter"]

    entities = []

    if adapter.adapter_type == "solo":
        # Solo adapter: expose registers D0000–D0006 and D2000–D2003
        solo_registers = [
            (0, "Power Status"),
            (1, "Mode Setting"),
            (2, "Temperature Setting"),
            (3, "Fan Speed Setting"),
            (4, "Louver Direction"),
            (5, "Fault Code"),
            (6, "Room Temperature"),
            (2000, "AC Brand"),
            (2001, "Outdoor Unit Address"),
            (2002, "Indoor Unit Address"),
            (2003, "Online Status"),
        ]
        for reg, desc in solo_registers:
            entities.append(
                SoloRegisterSensor(coordinator, entry, adapter, reg, desc)
            )
    else:
        # VRF Light/Pro adapter: gateway-level sensor
        entities.append(VrfGatewaySensor(coordinator, entry, adapter))

    async_add_entities(entities)


class SoloRegisterSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a single register on Solo adapter."""

    def __init__(self, coordinator, entry, adapter, register, description):
        super().__init__(coordinator)
        self._config_entry = entry
        self._adapter = adapter
        self._register = register
        self._attr_name = f"{adapter.name} {description}"
        self._attr_unique_id = f"{entry.entry_id}_solo_{register}"
        entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"solo_{entry_id}")},
            "manufacturer": "EGI",
            "model": f"{adapter.name}",
        }

    @property
    def native_value(self):
        """Return current value for this register."""
        data = self.coordinator.data or {}
        return data.get(self._register)

    async def async_update(self):
        """Fetch register value directly from adapter."""
        try:
            result = await self.hass.async_add_executor_job(
                lambda: self._adapter.read_register(self._register)
            )
            self._state = result
        except Exception as err:
            _LOGGER.error(
                "Error reading Solo register %s: %s", self._register, err
            )
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
            "identifiers": {(DOMAIN, f"gateway_{entry_id}")},
            "name": f"{self._coordinator.gateway_brand_name} VRF Gateway",
            "manufacturer": "EGI",
            "model": f"{self._adapter.name} - {self._coordinator.gateway_brand_name}",
            "sw_version": "1.0",
        }

    @property
    def extra_state_attributes(self):
        adapter_data = self._coordinator.adapter_info or {}
        brand_code = adapter_data.get("brand_code")
        return {
            "brand_code": brand_code,
            "brand_name": (
                self._adapter.get_brand_name(brand_code)
                if brand_code is not None
                else "Unknown"
            ),
            "supported_modes": self._decode_bitmask(
                adapter_data.get("supported_modes", 0),
                const.SUPPORTED_MODES,
            ),
            "supported_fan_speeds": self._decode_bitmask(
                adapter_data.get("supported_fan", 0),
                const.SUPPORTED_FAN_SPEEDS,
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
