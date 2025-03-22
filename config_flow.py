"""Config flow for EGI VRF."""

from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_BAUDRATE, DEFAULT_PARITY, DEFAULT_STOPBITS, DEFAULT_SLAVE

class EgiVRFConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="EGI VRF Gateway", data=user_input)

        schema = vol.Schema({
            vol.Required("port"): str,
            vol.Optional("baudrate", default=DEFAULT_BAUDRATE): int,
            vol.Optional("parity", default=DEFAULT_PARITY): vol.In(["E", "O", "N"]),
            vol.Optional("stopbits", default=DEFAULT_STOPBITS): int,
            vol.Optional("slave", default=DEFAULT_SLAVE): int
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
