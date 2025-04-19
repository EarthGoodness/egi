import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

class EgiVrfOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Safe, HA 2025+ options flow for EGI VRF."""

    async def async_step_init(self, user_input=None):
        """Initial options form: poll interval + optional restart/reset."""
        errors = {}
        poll_interval_default = self.config_entry.options.get("poll_interval", 2)

        if user_input is not None:
            updated_options = dict(self.config_entry.options)
            updated_options["poll_interval"] = user_input.get("poll_interval", poll_interval_default)

            # Handle optional actions
            if user_input.get("trigger_restart"):
                _LOGGER.info("User requested adapter restart for entry %s", self.config_entry.entry_id)
                await self._execute_adapter_command("restart_device")

            if user_input.get("trigger_factory_reset"):
                _LOGGER.warning("User requested factory reset for entry %s", self.config_entry.entry_id)
                await self._execute_adapter_command("factory_reset")

            return self.async_create_entry(title="", data=updated_options)

        # Form schema
        data_schema = vol.Schema({
            vol.Required("poll_interval", default=poll_interval_default): vol.All(
                int, vol.Range(min=1, max=60)
            ),
            vol.Optional("trigger_restart", default=False): bool,
            vol.Optional("trigger_factory_reset", default=False): bool,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "adapter_type": self.config_entry.data.get("adapter_type", "unknown").capitalize(),
                "connection_type": self.config_entry.data.get("connection_type", "unknown").upper(),
            }
        )

    async def _execute_adapter_command(self, command):
        """Call adapter restart or factory reset if supported."""
        entry_id = self.config_entry.entry_id
        adapter = self.hass.data.get("egi_vrf", {}).get(entry_id, {}).get("adapter")
        client = self.hass.data.get("egi_vrf", {}).get(entry_id, {}).get("client")

        if adapter and hasattr(adapter, command):
            _LOGGER.debug("Calling adapter.%s() for entry %s", command, entry_id)
            try:
                await self.hass.async_add_executor_job(getattr(adapter, command), client)
            except Exception as e:
                _LOGGER.error("Error running adapter.%s(): %s", command, e)
        else:
            _LOGGER.warning("Adapter or method %s not available for entry %s", command, entry_id)
