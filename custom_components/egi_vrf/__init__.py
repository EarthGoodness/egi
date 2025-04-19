# __init__.py
import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from . import const
from .coordinator import EgiVrfCoordinator
from .modbus_client import get_shared_client, EgiModbusClient
from .adapters import get_adapter

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "button", "sensor", "select"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(const.DOMAIN, {})

    adapter_type = entry.data.get("adapter_type", "light")
    adapter = get_adapter(adapter_type)
    _LOGGER.info("Initializing EGI VRF adapter type: %s", adapter_type)

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
            bytesize=entry.data.get("bytesize", const.DEFAULT_BYTESIZE),
        )
    else:
        client = _init_modbus_client(entry)
        if client is None:
            raise ConfigEntryNotReady("Modbus TCP connection failed")

    # Connect and scan
    connected = await hass.async_add_executor_job(client.connect)
    if not connected:
        raise ConfigEntryNotReady("Unable to connect to Modbus adapter")

    indoor_units = await hass.async_add_executor_job(adapter.scan_devices, client)
    if not indoor_units:
        _LOGGER.error("No indoor units detected for EGI VRF gateway.")
        return False

    update_interval = timedelta(seconds=entry.options.get("poll_interval", 2))

    coordinator = EgiVrfCoordinator(hass, client, adapter, indoor_units, update_interval)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Initial data refresh failed: %s", err)
        raise ConfigEntryNotReady from err

    hass.data[const.DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "adapter": adapter,
    }

    # Register service: set_system_time
    async def async_handle_set_time(call):
        entry_id = call.data.get("entry_id")
        adapter = hass.data[const.DOMAIN].get(entry_id, {}).get("adapter")
        client = hass.data[const.DOMAIN].get(entry_id, {}).get("client")
        if adapter and client and hasattr(adapter, "write_system_time"):
            await hass.async_add_executor_job(adapter.write_system_time, client)
            _LOGGER.info("System time set for adapter: %s", entry_id)
        else:
            _LOGGER.warning("Adapter or client not found for entry_id: %s", entry_id)

    hass.services.async_register(
        const.DOMAIN, "set_system_time", async_handle_set_time
    )

    # Register service: set_brand_code
    async def async_handle_set_brand(call):
        entry_id = call.data.get("entry_id")
        brand_code = call.data.get("brand_code")
        adapter = hass.data[const.DOMAIN].get(entry_id, {}).get("adapter")
        client = hass.data[const.DOMAIN].get(entry_id, {}).get("client")
        if adapter and client and hasattr(adapter, "write_brand_code"):
            await hass.async_add_executor_job(adapter.write_brand_code, client, brand_code)
            _LOGGER.info("Brand code %s written to adapter %s", brand_code, entry_id)
        else:
            _LOGGER.warning("Adapter or client not found for entry_id: %s", entry_id)

    hass.services.async_register(
        const.DOMAIN, "set_brand_code", async_handle_set_brand
    )

    # Register rescan service
    async def async_handle_rescan_service(call):
        entry_id = call.data.get("entry_id")
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            _LOGGER.error("Invalid entry_id provided for rescan: %s", entry_id)
            return
        coordinator = hass.data[const.DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_request_refresh()
        _LOGGER.info("Rescan completed for entry %s", entry.title)

    if not hass.services.has_service(const.DOMAIN, "scan_idus"):
        hass.services.async_register(
            const.DOMAIN,
            "scan_idus",
            async_handle_rescan_service,
        )

    # Register device in registry
    device_registry = async_get_device_registry(hass)
    gateway_id = f"gateway_{entry.entry_id}"
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(const.DOMAIN, gateway_id)},
        name="VRF Gateway",
        manufacturer="EGI",
        model="VRF Gateway light",
    )

    if coordinator.gateway_brand_code:
        device_registry.async_update_device(
            device.id,
            sw_version="1.0",
            configuration_url=None,
            name_by_user=f"{coordinator.gateway_brand_name} VRF Gateway"
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _init_modbus_client(entry):
    """TCP-only fallback. Use get_shared_client() for serial."""
    conn_type = entry.data.get("connection_type", "serial")
    slave_id = entry.data.get("slave_id", const.DEFAULT_SLAVE_ID)
    try:
        if conn_type != "tcp":
            _LOGGER.error("Serial should use get_shared_client().")
            return None
        client = EgiModbusClient(
            host=entry.data.get("host"),
            port=entry.data.get("port", 502),
            slave_id=slave_id,
        )
        return client
    except Exception as ex:
        _LOGGER.error("Modbus TCP initialization failed: %s", ex)
        return None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[const.DOMAIN].pop(entry.entry_id, {})
        coordinator = data.get("coordinator")
        if coordinator:
            coordinator.update_interval = None

        if not hass.data[const.DOMAIN]:
            hass.services.async_remove(const.DOMAIN, "scan_idus")
            hass.services.async_remove(const.DOMAIN, "set_brand_code")
            hass.services.async_remove(const.DOMAIN, "set_system_time")

    return unload_ok


@callback
def async_get_options_flow(config_entry):
    from .options_flow import EgiVrfOptionsFlowHandler
    return EgiVrfOptionsFlowHandler(config_entry)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.info("Configuration updated, reloading EGI VRF integration")
    await hass.config_entries.async_reload(entry.entry_id)

