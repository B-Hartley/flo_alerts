"""Config flow for Flo Alerts."""

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LOCATION
import voluptuous as vol

from . import locations
from .const import DOMAIN


class FloAlertsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure an existing Flo location."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Select a configured Flo location."""
        available = locations(self.hass)
        if not available:
            return self.async_abort(reason="no_flo")
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            if location in available:
                await self.async_set_unique_id(location)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Flo Alerts", data={CONF_LOCATION: location}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_LOCATION): vol.In(list(available))}),
        )
