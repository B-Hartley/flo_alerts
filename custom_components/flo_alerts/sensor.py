"""Outstanding Flo alerts sensor."""

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_LOCATION
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
import logging

from . import locations
from .api import active_alerts

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the alert count and detail attributes."""
    location = entry.data[CONF_LOCATION]

    async def update():
        try:
            client, _ = locations(hass)[location]
            return await active_alerts(client, location)
        except Exception as err:
            raise UpdateFailed("Unable to retrieve Flo alerts") from err

    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="Flo alerts", config_entry=entry,
        update_method=update, update_interval=timedelta(seconds=60),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    async_add_entities([AlertsSensor(coordinator, location)])


class AlertsSensor(CoordinatorEntity, SensorEntity):
    """Count outstanding alerts and expose their details."""

    _attr_name = "Flo active alerts"
    _attr_icon = "mdi:water-alert"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator, location):
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{location}_active_alerts"
        self._location = location

    @property
    def native_value(self):
        """Return outstanding count."""
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return normalized alerts."""
        return {
            "location_id": self._location,
            "alerts": self.coordinator.data,
            "critical_count": sum(a["severity"] == "critical" for a in self.coordinator.data),
        }
