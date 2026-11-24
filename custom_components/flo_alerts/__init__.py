"""Flo Alerts companion integration."""

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .api import acknowledge, active_alerts
from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def locations(hass: HomeAssistant) -> dict[str, tuple[Any, list]]:
    """Discover loaded Flo locations."""
    found = {}
    for entry in hass.config_entries.async_entries("flo"):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        for device in runtime.devices:
            found.setdefault(device.location_id, (runtime.client, []))[1].append(device)
    return found


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register integration actions."""
    lock = asyncio.Lock()

    def resolve(call: ServiceCall):
        configured = {
            entry.data[CONF_LOCATION]
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state.value == "loaded"
        }
        found = {key: value for key, value in locations(hass).items() if key in configured}
        location = call.data.get("location_id")
        if location is None and len(found) == 1:
            location = next(iter(found))
        if location not in found:
            raise ServiceValidationError("Select a loaded Flo Alerts location")
        return location, *found[location]

    async def get_alerts(call: ServiceCall) -> dict:
        """Return outstanding alerts."""
        location, client, _ = resolve(call)
        try:
            async with lock, asyncio.timeout(45):
                alerts = await active_alerts(client, location)
        except Exception as err:
            raise HomeAssistantError("Unable to retrieve Flo alerts") from err
        return {"location_id": location, "count": len(alerts), "alerts": alerts}

    async def clear_alert(call: ServiceCall) -> dict:
        """Acknowledge one alarm type and verify the result."""
        location, client, devices = resolve(call)
        alarm_id = call.data["alarm_id"]
        try:
            async with lock, asyncio.timeout(45):
                remaining = await acknowledge(client, location, alarm_id)
        except Exception as err:
            raise HomeAssistantError(
                "Acknowledgement failed or could not be verified; check alerts before retrying"
            ) from err
        await asyncio.gather(
            *(device.async_request_refresh() for device in devices),
            return_exceptions=True,
        )
        return {
            "location_id": location,
            "alarm_id": alarm_id,
            "still_triggered": any(a["alarm_id"] == alarm_id for a in remaining),
            "remaining_count": len(remaining),
            "remaining_alerts": remaining,
        }

    base = {vol.Optional("location_id"): cv.string}
    service.async_register_admin_service(
        hass, DOMAIN, "get_alerts", get_alerts,
        schema=vol.Schema(base), supports_response=SupportsResponse.ONLY,
    )
    service.async_register_admin_service(
        hass, DOMAIN, "clear_alert", clear_alert,
        schema=vol.Schema({**base, vol.Required("alarm_id"): vol.All(int, vol.Range(min=1))}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Validate the selected location."""
    if entry.data[CONF_LOCATION] not in locations(hass):
        raise ConfigEntryNotReady("Selected Flo location is not loaded")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the location."""
    return True
