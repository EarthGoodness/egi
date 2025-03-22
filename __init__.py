"""EGI VRF Modbus RTU Integration initialization."""
import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

from . import const, modbus_client, coordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["button", "climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up EGI VRF integration from a config entry."""
    hass.data.setdefault(const.DOMAIN, {})

    # Initialize Modbus client in a thread-safe manner
    client = await hass.async_add_executor_job(_init_modbus_client, entry)
    if client is None:
        raise ConfigEntryNotReady("Modbus connection failed")

    # Scan for indoor units
    indoor_units = await hass.async_add_executor_job(_scan_devices, client)
    if not indoor_units:
        _LOGGER.error("No indoor units detected for EGI VRF gateway.")
        client.close()
        return False

    _LOGGER.info("Detected %d indoor units: %s", len(indoor_units), [f"{s}-{i}" for s, i in indoor_units])

    # Set up the coordinator
    vrf_coordinator = coordinator.EgiVrfCoordinator(hass, client, indoor_units)
    try:
        await vrf_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Initial data refresh failed: %s", err)
        client.close()
        raise ConfigEntryNotReady from err

    # Store coordinator and client
    hass.data[const.DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": vrf_coordinator,
    }

    # Register rescan service
    async def async_handle_rescan_service(call):
        await _handle_rescan_service(hass, call.data)

    hass.services.async_register(
        const.DOMAIN,
        "scan_idus",
        async_handle_rescan_service,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add listener for config updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _init_modbus_client(entry):
    """Synchronously initialize the Modbus client."""
    conn_type = entry.data.get("connection_type", "serial")
    slave_id = entry.data.get("slave_id", const.DEFAULT_SLAVE_ID)
    try:
        if conn_type == "serial":
            client = modbus_client.EgiModbusClient(
                port=entry.data.get("port", const.DEFAULT_PORT),
                baudrate=entry.data.get("baudrate", const.DEFAULT_BAUDRATE),
                parity=entry.data.get("parity", const.DEFAULT_PARITY),
                stopbits=entry.data.get("stopbits", const.DEFAULT_STOPBITS),
                bytesize=entry.data.get("bytesize", const.DEFAULT_BYTESIZE),
                slave_id=slave_id,
            )
        else:  # TCP
            client = modbus_client.EgiModbusClient(
                host=entry.data.get("host"),
                port=entry.data.get("port", 502),
                slave_id=slave_id,
            )
        if not client.connect():
            _LOGGER.error("Unable to connect to EGI VRF gateway")
            client.close()
            return None
    except Exception as ex:
        _LOGGER.error("Modbus client initialization failed: %s", ex)
        return None

    return client


def _scan_devices(client):
    """Synchronously scan available indoor units."""
    found = []
    for system in range(4):  # systems 1 to 4
        for index in range(32):  # IDUs 0-31 per system
            addr = (system * 32 + index) * const.STATUS_REG_COUNT
            result = client.read_holding_registers(addr, const.STATUS_REG_COUNT)
            if result and any(val != 0 for val in result):
                found.append((system, index))
    return found


async def _handle_rescan_service(hass, data):
    """Handle service call to rescan indoor units."""
    entry_id = data.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        _LOGGER.error("Invalid entry_id provided for rescan: %s", entry_id)
        return
    coordinator = hass.data[const.DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_request_refresh()
    _LOGGER.info("Rescan completed for entry %s", entry.title)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry properly."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[const.DOMAIN].pop(entry.entry_id, {})
        client = data.get("client")
        if client:
            client.close()
        coordinator = data.get("coordinator")
        if coordinator:
            coordinator.update_interval = None

        # Unregister service if no entries remain
        if not hass.data[const.DOMAIN]:
            hass.services.async_remove(const.DOMAIN, "scan_idus")
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Reload integration upon config update."""
    _LOGGER.info("Configuration updated, reloading EGI VRF integration")
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def async_get_options_flow(config_entry):
    """Return the options flow handler."""
    from .options_flow import EgiVrfOptionsFlowHandler
    return EgiVrfOptionsFlowHandler()