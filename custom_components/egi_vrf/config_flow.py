"""Config flow for EGI VRF integration."""
import logging
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from . import const, modbus_client
from .options_flow import EgiVrfOptionsFlowHandler  # <-- Added this import

_LOGGER = logging.getLogger(__name__)

class EgiVrfConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle a config flow for EGI VRF Modbus integration."""
    VERSION = 1

    def __init__(self):
        self._connection_type = None

    async def async_step_user(self, user_input=None):
        """First step: choose connection type."""
        errors = {}
        if user_input is not None:
            self._connection_type = user_input.get("connection_type")
            if self._connection_type == "serial":
                return await self.async_step_serial()
            elif self._connection_type == "tcp":
                return await self.async_step_tcp()
            else:
                errors["base"] = "invalid_connection_type"
        data_schema = vol.Schema({
            vol.Required("connection_type", default="serial"): vol.In(["serial", "tcp"])
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_serial(self, user_input=None):
        """Handle the serial connection configuration step."""
        errors = {}
        if user_input is not None:
            user_input["connection_type"] = "serial"
            error = await self._async_test_connection(user_input)
            if error is None:
                return self.async_create_entry(title=f"EGI VRF (Serial {user_input.get('port')})", data=user_input)
            else:
                errors["base"] = error
        data_schema = vol.Schema({
            vol.Required("port", default=const.DEFAULT_PORT): str,
            vol.Optional("baudrate", default=const.DEFAULT_BAUDRATE): int,
            vol.Optional("parity", default=const.DEFAULT_PARITY): vol.In(["N", "E", "O"]),
            vol.Optional("stopbits", default=const.DEFAULT_STOPBITS): vol.All(int, vol.In([1, 2])),
            vol.Optional("bytesize", default=const.DEFAULT_BYTESIZE): vol.All(int, vol.In([7, 8])),
            vol.Optional("slave_id", default=const.DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247))
        })
        return self.async_show_form(step_id="serial", data_schema=data_schema, errors=errors)

    async def async_step_tcp(self, user_input=None):
        """Handle the TCP connection configuration step."""
        errors = {}
        if user_input is not None:
            user_input["connection_type"] = "tcp"
            error = await self._async_test_connection(user_input)
            if error is None:
                return self.async_create_entry(title=f"EGI VRF (TCP {user_input.get('host')}:{user_input.get('port')})", data=user_input)
            else:
                errors["base"] = error
        data_schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=502): int,
            vol.Optional("slave_id", default=const.DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247))
        })
        return self.async_show_form(step_id="tcp", data_schema=data_schema, errors=errors)

    async def _async_test_connection(self, config):
        """Test the modbus connection with given config. Returns error string or None if success."""
        def _try_connect():
            try:
                if config.get("connection_type") == "serial":
                    client = modbus_client.EgiModbusClient(
                        port=config.get("port"),
                        baudrate=config.get("baudrate", const.DEFAULT_BAUDRATE),
                        parity=config.get("parity", const.DEFAULT_PARITY),
                        stopbits=config.get("stopbits", const.DEFAULT_STOPBITS),
                        bytesize=config.get("bytesize", const.DEFAULT_BYTESIZE),
                        slave_id=config.get("slave_id", const.DEFAULT_SLAVE_ID)
                    )
                else:
                    client = modbus_client.EgiModbusClient(
                        host=config.get("host"),
                        port=config.get("port", 502),
                        slave_id=config.get("slave_id", const.DEFAULT_SLAVE_ID)
                    )
                if not client.connect():
                    return "cannot_connect"
                result = client.read_holding_registers(0, 1)
                client.close()
                if result is None:
                    return "no_response"
            except Exception as e:
                _LOGGER.error("Connection test failed: %s", e)
                return "cannot_connect"
            return None
        return await self.hass.async_add_executor_job(_try_connect)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EgiVrfOptionsFlowHandler()

