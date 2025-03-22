"""Config flow for EGI VRF integration."""
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import DOMAIN, CONF_PORT, CONF_BAUDRATE, CONF_PARITY, CONF_STOPBITS, CONF_SLAVE_ID, CONF_POLL_INTERVAL, \
    DEFAULT_BAUDRATE, DEFAULT_PARITY, DEFAULT_STOPBITS, DEFAULT_SLAVE_ID, DEFAULT_POLL_INTERVAL

# Mapping of parity display names to single-letter codes
PARITY_OPTIONS = {"None": "N", "Even": "E", "Odd": "O"}

class EgiVrfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EGI VRF."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of configuration."""
        errors = {}
        if user_input is not None:
            # Basic validation for required port
            port = user_input.get(CONF_PORT)
            if not port:
                errors["base"] = "port_required"
            if not errors:
                # Convert parity to single-letter code
                parity = user_input.get(CONF_PARITY, DEFAULT_PARITY)
                if parity in PARITY_OPTIONS:
                    user_input[CONF_PARITY] = PARITY_OPTIONS[parity]
                return self.async_create_entry(title=f"EGI VRF ({port})", data=user_input)
        # Show the form with default values
        default_port = "/dev/ttyUSB0"
        data_schema = vol.Schema({
            vol.Required(CONF_PORT, default=default_port): str,
            vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.Coerce(int),
            vol.Optional(CONF_PARITY, default="Even"): vol.In(list(PARITY_OPTIONS.keys())),
            vol.Optional(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
            vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.Coerce(int),
            vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.Coerce(int),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EgiVrfOptionsFlowHandler(config_entry)

class EgiVrfOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for existing EGI VRF config entry."""

    async def async_step_init(self, user_input=None):
        """Manage the integration options."""
        if user_input is not None:
            # Convert parity display name back to single-letter code
            parity_name = user_input.get(CONF_PARITY)
            if parity_name in PARITY_OPTIONS:
                user_input[CONF_PARITY] = PARITY_OPTIONS[parity_name]
            return self.async_create_entry(title="", data=user_input)

        # Current settings as defaults
        current = {**self.config_entry.data, **(self.config_entry.options or {})}
        data_schema = vol.Schema({
            vol.Optional(CONF_BAUDRATE, default=current.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)): vol.Coerce(int),
            vol.Optional(CONF_PARITY, default=self._parity_display(current.get(CONF_PARITY, DEFAULT_PARITY))): vol.In(list(PARITY_OPTIONS.keys())),
            vol.Optional(CONF_STOPBITS, default=current.get(CONF_STOPBITS, DEFAULT_STOPBITS)): vol.In([1, 2]),
            vol.Optional(CONF_SLAVE_ID, default=current.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)): vol.Coerce(int),
            vol.Optional(CONF_POLL_INTERVAL, default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): vol.Coerce(int),
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)

    def _parity_display(self, parity_char):
        """Helper to get parity display name from single-letter code."""
        for name, char in PARITY_OPTIONS.items():
            if parity_char and parity_char.upper() == char:
                return name
        return "None"
