"""Sensor platform for EGI Adapter integration."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import const

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up EGI monitoring sensors and adapter config/info sensors."""
    # Monitor-only mode: skip sensors
    if entry.data.get("adapter_type") == "none":
        _LOGGER.debug(
            "Monitor-only mode: skipping EGI sensors for entry %s", entry.entry_id
        )
        return

    entry_data = hass.data.get(const.DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.error(
            "No data found for entry %s, skipping EGI sensors", entry.entry_id
        )
        return

    coordinator = entry_data["coordinator"]
    adapter = entry_data["adapter"]
    gateway_id = f"gateway_{entry.entry_id}"

    async_add_entities([
        SetupTimeSensor(coordinator, entry.entry_id, gateway_id),
        PollIntervalSensor(coordinator, entry.entry_id, gateway_id),
        UpdateTimeSensor(coordinator, entry.entry_id, gateway_id),
        LogLevelSensor(entry.entry_id, adapter, gateway_id),
        AdapterConfigSensor(entry, coordinator, gateway_id),
        AdapterInfoSensor(entry, coordinator, adapter, gateway_id),
    ])

class BaseEgiSensor(SensorEntity):
    """Common bits for all EGI sensors."""
    def __init__(self, entry_id: str, gateway_id: str):
        self._entry_id = entry_id
        self._attr_device_info = {"identifiers": {(const.DOMAIN, gateway_id)}}

class SetupTimeSensor(BaseEgiSensor):
    """How long setup took (seconds)."""
    def __init__(self, coordinator, entry_id, gateway_id):
        super().__init__(entry_id, gateway_id)
        self._coordinator = coordinator
        self._attr_name = "EGI Setup Time"
        self._attr_unique_id = f"{entry_id}_setup_time"
        self._attr_unit_of_measurement = "s"

    @property
    def state(self):
        duration = getattr(self._coordinator, "setup_duration", None)
        return round(duration, 2) if duration is not None else None

class PollIntervalSensor(BaseEgiSensor):
    """Configured poll interval (seconds)."""
    def __init__(self, coordinator, entry_id, gateway_id):
        super().__init__(entry_id, gateway_id)
        self._coordinator = coordinator
        self._attr_name = "EGI Poll Interval"
        self._attr_unique_id = f"{entry_id}_poll_interval"
        self._attr_unit_of_measurement = "s"

    @property
    def state(self):
        return self._coordinator.update_interval.total_seconds()

class UpdateTimeSensor(BaseEgiSensor):
    """Measured duration of the last update (seconds)."""
    def __init__(self, coordinator, entry_id, gateway_id):
        super().__init__(entry_id, gateway_id)
        self._coordinator = coordinator
        self._attr_name = "EGI Last Update Duration"
        self._attr_unique_id = f"{entry_id}_last_update_duration"
        self._attr_unit_of_measurement = "s"

    @property
    def state(self):
        duration = getattr(self._coordinator, "last_update_duration", None)
        return round(duration, 2) if duration is not None else None

class LogLevelSensor(BaseEgiSensor):
    """Current log level for this adapter."""
    def __init__(self, entry_id, adapter, gateway_id):
        super().__init__(entry_id, gateway_id)
        self._adapter = adapter
        self._attr_name = "EGI Adapter Log Level"
        self._attr_unique_id = f"{entry_id}_log_level"

    @property
    def state(self):
        logger_name = f"custom_components.egi.adapter.{self._adapter.__class__.__name__}"
        level_no = logging.getLogger(logger_name).getEffectiveLevel()
        return logging.getLevelName(level_no)

class AdapterConfigSensor(BaseEgiSensor):
    """Exposes all static adapter configuration settings."""
    def __init__(self, entry: ConfigEntry, coordinator, gateway_id):
        super().__init__(entry.entry_id, gateway_id)
        self._conf = entry.data
        self._coordinator = coordinator
        self._attr_name = "EGI Adapter Config"
        self._attr_unique_id = f"{entry.entry_id}_adapter_config"

    @property
    def state(self):
        return self._conf.get("adapter_type", "unknown")

    @property
    def extra_state_attributes(self):
        attrs = {
            "connection_type": self._conf.get("connection_type"),
            "slave_id": self._conf.get("slave_id"),
            "poll_interval_s": self._coordinator.update_interval.total_seconds(),
        }
        if self._conf.get("connection_type") == "serial":
            attrs.update({
                "port": self._conf.get("port"),
                "baudrate": self._conf.get("baudrate"),
                "parity": self._conf.get("parity"),
                "stopbits": self._conf.get("stopbits"),
                "bytesize": self._conf.get("bytesize"),
            })
        else:
            host = self._conf.get("host", "")
            port = self._conf.get("port", 502)
            attrs["host"] = f"{host}:{port}"
        return attrs

class AdapterInfoSensor(BaseEgiSensor):
    """Exposes all decoded adapter data retrieved via Modbus."""
    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        adapter,
        gateway_id: str
    ):
        super().__init__(entry.entry_id, gateway_id)
        self._coordinator = coordinator
        self._adapter = adapter
        self._attr_name = "EGI Adapter Info"
        self._attr_unique_id = f"{entry.entry_id}_adapter_info"

    @property
    def state(self):
        return getattr(self._coordinator, "gateway_brand_name", None)

    @property
    def extra_state_attributes(self):
        raw = getattr(self._coordinator, "adapter_info", {}) or {}
        try:
            decoded = self._adapter.decode_adapter_info(raw)
        except Exception as e:
            _LOGGER.error("Failed to decode adapter info: %s", e)
            decoded = raw
        return decoded
