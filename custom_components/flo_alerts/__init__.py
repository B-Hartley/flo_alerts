"""Flo Alerts companion integration."""

import asyncio
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LOCATION, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er, service

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
    await hass.http.async_register_static_paths([
        StaticPathConfig("/flo_alerts/flo-alerts-card.js", str(Path(__file__).parent / "www" / "flo-alerts-card.js"), False),
    ])
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
                if "event_ids" in call.data:
                    current = await active_alerts(client, location)
                    expected = set(call.data["event_ids"])
                    if expected != {a["event_id"] for a in current if a["alarm_id"] == alarm_id}:
                        raise ServiceValidationError("Alerts changed; refresh and review")
                remaining = await acknowledge(client, location, alarm_id)
        except Exception as err:
            raise HomeAssistantError(
                "Acknowledgement failed or could not be verified; check alerts before retrying"
            ) from err
        await asyncio.gather(
            *(device.async_request_refresh() for device in devices),
            return_exceptions=True,
        )
        await refresh_location(location)
        return {
            "location_id": location,
            "alarm_id": alarm_id,
            "still_triggered": any(a["alarm_id"] == alarm_id for a in remaining),
            "remaining_count": len(remaining),
            "remaining_alerts": remaining,
        }

    async def refresh_location(location):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_LOCATION] == location and entry.state.value == "loaded":
                await entry.runtime_data.async_request_refresh()

    async def refresh(call):
        location, _, _ = resolve(call)
        await refresh_location(location)

    async def clear_all(call):
        location, client, devices = resolve(call)
        restore = call.data.get('restore_water', False)
        valve = call.data.get('valve_entity_id')
        guards = call.data.get('leak_sensor_ids', [])

        def check_restore():
            if not valve or not guards:
                raise ServiceValidationError('Valve and physical leak sensors must be specified')
            if any(not hass.states.is_state(sensor, 'off') for sensor in guards):
                raise ServiceValidationError('Physical leak detected or sensor unavailable; water remains off')
            if not hass.states.is_state(valve, 'off'):
                raise ServiceValidationError('Valve is not confirmed closed')

        try:
            async with lock, asyncio.timeout(45):
                before = await active_alerts(client, location)
                expected = set(call.data["event_ids"])
                if expected != {a["event_id"] for a in before}:
                    raise ServiceValidationError("Alerts changed; refresh and review before acknowledging")
                if restore:
                    check_restore()
                    registry = er.async_get(hass)
                    valve_entry = registry.async_get(valve)
                    matching = [
                        device for device in devices
                        if valve_entry is not None
                        and valve_entry.platform == "flo"
                        and valve_entry.unique_id == f"{device.mac_address}_shutoff_valve"
                    ]
                    if len(matching) != 1 or not any(
                        a["alarm_id"] == 83 and a["device_id"] == matching[0].id
                        for a in before
                    ):
                        raise ServiceValidationError("No matching automatic shutoff alert; water remains off")
                if before:
                    from .api import BASE
                    await client._request("post", BASE + "/action", json={
                        "locationId": location,
                        "alarmIds": sorted({a["alarm_id"] for a in before}),
                        "snoozeSeconds": 0,
                    })
                remaining = await active_alerts(client, location)
                if restore and not remaining:
                    check_restore()
                    await hass.services.async_call(
                        "switch", "turn_on", {"entity_id": valve},
                        blocking=True, context=call.context,
                    )
        except ServiceValidationError:
            await refresh_location(location)
            raise
        except Exception as err:
            raise HomeAssistantError("Unable to verify acknowledgement; refresh before retrying") from err
        await asyncio.gather(
            *(device.async_request_refresh() for device in devices),
            return_exceptions=True,
        )
        await refresh_location(location)
        if remaining:
            raise HomeAssistantError("Some alerts remain outstanding; review the refreshed list")

    base = {vol.Optional("location_id"): cv.string}
    service.async_register_admin_service(
        hass, DOMAIN, "get_alerts", get_alerts,
        schema=vol.Schema(base), supports_response=SupportsResponse.ONLY,
    )
    service.async_register_admin_service(
        hass, DOMAIN, "clear_alert", clear_alert,
        schema=vol.Schema({**base, vol.Required("alarm_id"): vol.All(int, vol.Range(min=1)), vol.Optional("event_ids"): [cv.string]}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_admin_service(
        hass, DOMAIN, "refresh", refresh, schema=vol.Schema(base),
    )
    service.async_register_admin_service(
        hass, DOMAIN, "clear_all_alerts", clear_all,
        schema=vol.Schema({**base, vol.Required("event_ids"): [cv.string],
                           vol.Optional("restore_water", default=False): cv.boolean,
                           vol.Optional("valve_entity_id"): cv.entity_id,
                           vol.Optional("leak_sensor_ids"): [cv.entity_id]}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Validate the selected location."""
    if entry.data[CONF_LOCATION] not in locations(hass):
        raise ConfigEntryNotReady("Selected Flo location is not loaded")
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the location."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
