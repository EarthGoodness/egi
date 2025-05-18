import logging
from .modbus_client import get_shared_client
from .adapters import get_adapter
from . import const

_LOGGER = logging.getLogger(__name__)

DEFAULT_SLAVES = list(range(1, 11))  # Default scan range if not specified

async def discover_adapters(hass, config):
    """Scan a line or TCP network for EGI-compatible Modbus devices and create config entries."""
    connection_type = config.get("connection_type")
    slave_range = config.get("slave_range", DEFAULT_SLAVES)

    if connection_type not in ("serial", "tcp"):
        _LOGGER.warning("Unsupported connection_type: %s", connection_type)
        return []

    discovered = []
    attempted = 0

    for slave_id in slave_range:
        attempted += 1
        try:
            if connection_type == "serial":
                client = get_shared_client(
                    connection_type="serial",
                    slave_id=slave_id,
                    port=config.get("port"),
                    baudrate=config.get("baudrate", 9600),
                    parity=config.get("parity", "E"),
                    stopbits=config.get("stopbits", 1),
                    bytesize=config.get("bytesize", 8),
                )
            else:
                client = get_shared_client(
                    connection_type="tcp",
                    slave_id=slave_id,
                    host=config.get("host"),
                    port=config.get("port", 502),
                )

            await hass.async_add_executor_job(client.connect)
            _LOGGER.debug("Connected to slave %d, attempting identification...", slave_id)

            found_match = False
            for adapter_type in ("light", "pro", "solo"):
                adapter = get_adapter(adapter_type)
                _LOGGER.debug("Trying adapter type '%s' at slave %d", adapter_type, slave_id)
                info = await hass.async_add_executor_job(adapter.read_adapter_info, client)
                if not info:
                    _LOGGER.debug("Adapter type '%s' at slave %d gave no info response", adapter_type, slave_id)
                _LOGGER.debug("Adapter '%s' at slave %d returned: %s", adapter_type, slave_id, info)

                if info and info.get("brand_code") is not None:
                    # Avoid duplicate config entry creation
                    already_exists = False
                    for entry in hass.config_entries.async_entries(domain=const.DOMAIN):
                        if (
                            entry.data.get("adapter_type") == adapter_type and
                            entry.data.get("connection_type") == connection_type and
                            entry.data.get("slave_id") == slave_id and
                            entry.data.get("port") == config.get("port") and
                            entry.data.get("host") == config.get("host")
                        ):
                            already_exists = True
                            _LOGGER.info("Adapter already configured: %s", entry.data)
                            break

                    if already_exists:
                        found_match = True
                        break

                    _LOGGER.info("Discovered %s adapter at slave %d: %s", adapter_type, slave_id, info)

                    discovery_data = {
                        "adapter_type": adapter_type,
                        "connection_type": connection_type,
                        "slave_id": slave_id,
                    }
                    if connection_type == "serial":
                        discovery_data.update({
                            "port": config.get("port"),
                            "baudrate": config.get("baudrate", 9600),
                            "parity": config.get("parity", "E"),
                            "stopbits": config.get("stopbits", 1),
                            "bytesize": config.get("bytesize", 8),
                        })
                    else:
                        discovery_data.update({
                            "host": config.get("host"),
                            "port": config.get("port", 502),
                        })

                    await hass.config_entries.flow.async_init(
                        const.DOMAIN,
                        context={"source": "user"},
                        data=discovery_data
                    )

                    discovered.append(discovery_data)
                    found_match = True
                    break  # only break if an actual adapter match was found

            if not found_match:
                _LOGGER.debug("No matching adapter found at slave %d", slave_id)

        except Exception as e:
            _LOGGER.warning("No response from slave %d (%s): %s", slave_id, connection_type, e)
            continue

    _LOGGER.info("Discovery summary: tried %d slaves, found %d adapters", attempted, len(discovered))
    return discovered
