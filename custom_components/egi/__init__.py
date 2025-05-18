"""
EGI Adapter integration init
"""
import logging
import time
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from . import const
from .coordinator import EgiAdapterCoordinator
from .modbus_client import get_shared_client, EgiModbusClient
from .adapters import get_adapter

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "button", "sensor", "select"]

async def _async_config_entry_updated(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> None:
    """Reload the config entry when options are updated."""
    _LOGGER.debug("Config entry %s updated, reloading", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    """Set up a config entry."""
    hass.data.setdefault(const.DOMAIN, {})

    # Monitor-only mode: no adapter I/O, only select and sensor
    if entry.data.get("adapter_type") == "none":
        _LOGGER.info(
            "Monitor-only mode: skipping adapter setup for %s",
            entry.entry_id
        )
        device_registry = async_get_device_registry(hass)
        gateway_id = f"gateway_{entry.entry_id}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(const.DOMAIN, gateway_id)},
            name="EGI Monitoring",
            manufacturer="EGI",
            model="Logging Dashboard Only"
        )

        # Forward only sensor and select platforms
        await hass.config_entries.async_forward_entry_setups(
            entry, ["sensor", "select"]
        )

        entry.async_on_unload(
            entry.add_update_listener(_async_config_entry_updated)
        )
        return True

    # Normal adapter setup
    start_time = time.perf_counter()
    adapter_type = entry.data.get("adapter_type", "light")
    adapter = get_adapter(adapter_type)
    _LOGGER.info("Initializing EGI adapter type: %s", adapter_type)

    connection_type = entry.data.get("connection_type", "serial")
    slave_id = entry.data.get("slave_id", const.DEFAULT_SLAVE_ID)

    if connection_type == "serial":
        client = get_shared_client(
            connection_type="serial",
            slave_id=slave_id,
            port=entry.data.get("port"),
            baudrate=entry.data.get("baudrate", const.DEFAULT_BAUDRATE),
            parity=entry.data.get("parity", const.DEFAULT_PARITY),
            stopbits=entry.data.get("stopbits", const.DEFAULT_STOPBITS),
            bytesize=entry.data.get("bytesize", const.DEFAULT_BYTESIZE)
        )
    else:
        client = EgiModbusClient(
            host=entry.data.get("host"),
            port=entry.data.get("port", 502),
            unit_id=slave_id
        )

    # Connect
    connected = await hass.async_add_executor_job(client.connect)
    if not connected:
        raise ConfigEntryNotReady("Unable to connect to Modbus adapter")

    # Scan indoor units
    indoor_units = await hass.async_add_executor_job(
        adapter.scan_devices, client
    )
    if not indoor_units:
        _LOGGER.error("No indoor units detected for EGI adapter.")
        return False

    update_interval = timedelta(
        seconds=entry.options.get("poll_interval", 2)
    )
    coordinator = EgiAdapterCoordinator(
        hass, client, adapter, indoor_units, update_interval
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Initial data refresh failed: %s", err)
        raise ConfigEntryNotReady from err

    hass.data[const.DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "adapter": adapter
    }

    # Register services
    async def async_handle_set_time(call):
        eid = call.data.get("entry_id")
        data = hass.data[const.DOMAIN].get(eid, {})
        adapter_obj = data.get("adapter")
        client_obj = data.get("client")
        if adapter_obj and client_obj:
            await hass.async_add_executor_job(
                adapter_obj.write_system_time, client_obj
            )
            _LOGGER.info("System time set for adapter: %s", eid)
        else:
            _LOGGER.warning(
                "Adapter or client not found for entry_id: %s", eid
            )

    hass.services.async_register(
        const.DOMAIN, "set_system_time", async_handle_set_time
    )

    async def async_handle_set_brand(call):
        eid = call.data.get("entry_id")
        brand_code = call.data.get("brand_code")
        data = hass.data[const.DOMAIN].get(eid, {})
        adapter_obj = data.get("adapter")
        client_obj = data.get("client")
        if adapter_obj and client_obj:
            await hass.async_add_executor_job(
                adapter_obj.write_brand_code, client_obj, brand_code
            )
            _LOGGER.info(
                "Brand code %s written to adapter %s",
                brand_code, eid
            )
        else:
            _LOGGER.warning(
                "Adapter or client not found for entry_id: %s", eid
            )

    hass.services.async_register(
        const.DOMAIN, "set_brand_code", async_handle_set_brand
    )

    async def async_handle_rescan(call):
        eid = call.data.get("entry_id")
        if not hass.config_entries.async_get_entry(eid):
            _LOGGER.error(
                "Invalid entry_id provided for rescan: %s", eid
            )
            return
        await coordinator.async_request_refresh()
        _LOGGER.info("Rescan completed for entry %s", eid)

    if not hass.services.has_service(
        const.DOMAIN, "scan_idus"
    ):
        hass.services.async_register(
            const.DOMAIN, "scan_idus", async_handle_rescan
        )

    async def async_handle_set_log_level(call):
        import logging as _logging
        lvl = call.data.get("level", "INFO").upper()
        log_level = getattr(_logging, lvl, _logging.INFO)
        for name in [
            "custom_components.egi",
            "custom_components.egi.climate",
            "custom_components.egi.sensor",
            "custom_components.egi.select",
            "custom_components.egi.button",
            "custom_components.egi.modbus_client",
            "custom_components.egi.adapter"
        ]:
            _logging.getLogger(name).setLevel(log_level)
        _LOGGER.info("Set log level for EGI modules to %s", lvl)

    hass.services.async_register(
        const.DOMAIN, "set_log_level", async_handle_set_log_level
    )

    # Register device
    device_registry = async_get_device_registry(hass)
    gateway_id = f"gateway_{entry.entry_id}"
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(const.DOMAIN, gateway_id)},
        name=adapter.name,
        manufacturer="EGI",
        model=(
            f"{adapter.display_type} - "
            f"{adapter.get_brand_name(
                coordinator.gateway_brand_code
            )}"
        )
    )

    if coordinator.gateway_brand_code:
        device_registry.async_update_device(
            device.id,
            sw_version="1.0",
            name_by_user=adapter.name
        )

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS
    )

    # Update listener
    entry.async_on_unload(
        entry.add_update_listener(_async_config_entry_updated)
    )

    # Update entry title
    try:
        brand_name = adapter.get_brand_name(
            coordinator.gateway_brand_code
        )
    except Exception:
        brand_name = "Unknown"

    slave_id = getattr(
        client, "unit_id",
        entry.data.get("slave_id", "X")
    )
    port_str = (
        entry.data.get("port")
        if connection_type == "serial"
        else f"{entry.data.get('host')}:{entry.data.get('port', 502)}"
    )
    new_title = (
        f"{adapter.name} - {brand_name}"
        f" (ID {slave_id} / {port_str})"
    )
    hass.config_entries.async_update_entry(entry, title=new_title)

    # Record setup duration
    duration = time.perf_counter() - start_time
    coordinator.setup_duration = duration
    _LOGGER.debug(
        "Completed async_setup_entry for %s in %.2f seconds",
        adapter.name, duration
    )

    return True

async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    """Unload a config entry and clean up all resources."""
    # Unload all platforms (including sensor and select in monitor-only)
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if not unload_ok:
        return False

    # Remove this entry's stored data
    hass.data[const.DOMAIN].pop(entry.entry_id, None)

    # Remove the device from the registry (covers both normal and monitor-only)
    try:
        device_registry = async_get_device_registry(hass)
        gateway_id = f"gateway_{entry.entry_id}"
        device_entry = device_registry.async_get_device(
            identifiers={(const.DOMAIN, gateway_id)}
        )
        if device_entry:
            device_registry.async_remove_device(device_entry.id)
            _LOGGER.debug(
                "Removed EGI Monitoring device %s for entry %s",
                gateway_id,
                entry.entry_id,
            )
    except Exception as e:
        _LOGGER.warning(
            "Could not remove device for entry %s: %s", entry.entry_id, e
        )

    # If no entries remain, remove custom services
    if not hass.data[const.DOMAIN]:
        for svc in [
            "set_system_time",
            "set_brand_code",
            "scan_idus",
            "set_log_level",
        ]:
            if hass.services.has_service(const.DOMAIN, svc):
                hass.services.async_remove(const.DOMAIN, svc)

    _LOGGER.debug("Unloaded EGI Adapter entry %s", entry.entry_id)
    return True
