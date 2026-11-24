# Flo Alerts

Experimental companion to Home Assistant's built-in Moen Flo integration. No additional credentials or YAML configuration.

[Open in Home Assistant Marketplace](https://my.home-assistant.io/redirect/marketplace_repository/?owner=B-Hartley&repository=flo_alerts&category=integration)

## Installation

Requires Home Assistant 2026.11 or later. In Settings > Marketplace choose Add from link and enter https://github.com/B-Hartley/flo_alerts. Install, restart if prompted, then go to Settings > Devices & services > Add integration > Flo Alerts. Select your existing Flo location. Keep the original Flo integration installed.

## Actions

Use Developer Tools > Actions: `flo_alerts.get_alerts` retrieves outstanding warning and critical alerts. `flo_alerts.clear_alert` accepts the numeric `alarm_id` from that response. Specify `location_id` if multiple locations are configured. Both actions require administrator access.

Investigate the underlying cause before acknowledging. An alarm type ID is not a unique event ID. Multiple events of the same type may be affected. The action requests zero snooze seconds and verifies remaining alerts; it does not explicitly change the valve or mode. If a write fails, retrieve alerts before retrying.

## Status

Development preview 0.2.0. Live compatibility with the built-in Flo runtime and private aioflo request method is not yet verified. Dashboard entities and bulk acknowledgement are not yet implemented. No account credentials or personal captures are included.

## Development

Run `python -m unittest discover -s tests` and `ruff check .`. See [Home Assistant development guidelines](https://developers.home-assistant.io/docs/development_guidelines/).
