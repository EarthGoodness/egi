import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_BYTESIZE,
    DEFAULT_SLAVE_ID,
)

_LOGGER = logging.getLogger(__name__)

class EgiVrfOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for EGI VRF."""

    def __init__(self):
        """Initialize the options flow."""
        self.connection_type = None

    async def async_step_init(self, user_input=None):
        """First step to choose the connection type."""
        if user_input is not None:
            self.connection_type = user_input["connection_type"]
            return await self.async_step_connection_settings()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("connection_type", default=self.config_entry.data.get("connection_type", "serial")): vol.In(["serial", "tcp"]),
            }),
        )

    async def async_step_connection_settings(self, user_input=None):
        """Second step to configure connection settings and poll interval."""
        errors = {}

        if user_input is not None:
            updated_data = self.config_entry.data.copy()
            updated_options = self.config_entry.options.copy()

            updated_data["connection_type"] = self.connection_type
            updated_data.update(user_input)

            # Move poll_interval to options
            poll_interval = user_input.get("poll_interval", 2)
            updated_options["poll_interval"] = poll_interval
            updated_data.pop("poll_interval", None)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=updated_data, options=updated_options
            )

            return self.async_create_entry(title="", data={})

        # Define schema defaults
        poll_interval_default = self.config_entry.options.get("poll_interval", 2)
        slave_id_default = self.config_entry.data.get("slave_id", DEFAULT_SLAVE_ID)

        if self.connection_type == "serial":
            data_schema = vol.Schema({
                vol.Required("port", default=self.config_entry.data.get("port", DEFAULT_PORT)): str,
                vol.Optional("baudrate", default=self.config_entry.data.get("baudrate", DEFAULT_BAUDRATE)): int,
                vol.Optional("parity", default=self.config_entry.data.get("parity", DEFAULT_PARITY)): vol.In(["N", "E", "O"]),
                vol.Optional("stopbits", default=self.config_entry.data.get("stopbits", DEFAULT_STOPBITS)): vol.All(int, vol.In([1, 2])),
                vol.Optional("bytesize", default=self.config_entry.data.get("bytesize", DEFAULT_BYTESIZE)): vol.All(int, vol.In([7, 8])),
                # Slave ID now numeric input, no slider
                vol.Required("slave_id", default=slave_id_default): vol.Coerce(int),
                # Poll interval now as slider input
                vol.Required("poll_interval", default=poll_interval_default): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=60)
                ),
            })
        else:  # TCP
            data_schema = vol.Schema({
                vol.Required("host", default=self.config_entry.data.get("host", "")): str,
                vol.Required("port", default=self.config_entry.data.get("port", 502)): int,
                vol.Required("slave_id", default=slave_id_default): vol.Coerce(int),
                vol.Required("poll_interval", default=poll_interval_default): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=60)
                ),
            })

        return self.async_show_form(
            step_id="connection_settings",
            data_schema=data_schema,
            errors=errors,
        )
