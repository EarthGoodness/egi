"""EGI VRF Custom Integration - connects to VRF Gateway via Modbus."""
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .const import DOMAIN, CONF_PORT, CONF_BAUDRATE, CONF_PARITY, CONF_STOPBITS, CONF_SLAVE_ID, CONF_POLL_INTERVAL, \
    DEFAULT_BAUDRATE, DEFAULT_PARITY, DEFAULT_STOPBITS, DEFAULT_SLAVE_ID, DEFAULT_POLL_INTERVAL
from .modbus_client import EgiVrfModbusClient
from .coordinator import EgiVrfCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "button"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up via YAML (not supported, use UI config flow)."""
    return True  # no YAML support

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up EGI VRF from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    # Gather config entry parameters
    port = entry.data.get(CONF_PORT)
    baudrate = entry.data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
    parity_conf = entry.data.get(CONF_PARITY, DEFAULT_PARITY)
    parity = parity_conf if len(parity_conf) == 1 else (parity_conf[0].upper() if parity_conf.lower() != "none" else "N")
    stopbits = entry.data.get(CONF_STOPBITS, DEFAULT_STOPBITS)
    slave_id = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
    poll_interval = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    # Initialize Modbus client for the gateway
    client = EgiVrfModbusClient(port=port, baudrate=baudrate, parity=parity, stopbits=stopbits, slave_id=slave_id)
    # Perform initial scan for IDUs
    scan_result = await hass.async_add_executor_job(client.scan_idus)
    if scan_result is None:
        _LOGGER.warning("Initial scan of EGI VRF indoor units failed; retrying later.")
        return False  # trigger ConfigEntryNotReady (HA will retry setup)

    # Create data coordinator and store it
    coordinator = EgiVrfCoordinator(hass, client, poll_interval)
    coordinator.entry_id = entry.entry_id
    coordinator.set_initial_units(scan_result)
    hass.data[DOMAIN][entry.entry_id] = {"client": client, "coordinator": coordinator}

    # Forward setup to platforms (climate and button)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register a service to allow manual scan trigger
    if not hass.services.has_service(DOMAIN, "scan_idus"):
        async def handle_scan_service(service_call):
            # Determine which entries to scan (all by default, or specific entry_id)
            target_entry_id = service_call.data.get("entry_id")
            entries_to_scan = []
            if target_entry_id:
                entries_to_scan = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == target_entry_id]
            if not entries_to_scan:
                entries_to_scan = hass.config_entries.async_entries(DOMAIN)
            for ent in entries_to_scan:
                data = hass.data[DOMAIN].get(ent.entry_id)
                if data:
                    coord = data["coordinator"]
                    await coord.async_scan_idus()
        hass.services.async_register(DOMAIN, "scan_idus", handle_scan_service)

    # Register devices in the Device Registry for the gateway and each unit
    device_registry = async_get_device_registry(hass)
    gateway_id = f"{DOMAIN}_{entry.entry_id}"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway_id)},
        name="EGI VRF Gateway",
        manufacturer="EGI",
        model="VRF Modbus Gateway"
    )
    for uid, info in scan_result.items():
        brand_code = info.get("brand_code")
        brand_name = "Unknown Brand" if brand_code is None else f"Brand 0x{brand_code:02X}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_unit_{uid}")},
            name=f"Indoor Unit {uid}",
            manufacturer=brand_name,
            via_device=(DOMAIN, gateway_id)
        )
    # Fetch initial data for climate entities
    await coordinator.async_config_entry_first_refresh()
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Close the Modbus connection
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        client = data.get("client")
        if client:
            await hass.async_add_executor_job(client.close)
    return True
