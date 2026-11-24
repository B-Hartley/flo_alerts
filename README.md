# Flo Alerts

Experimental companion to Home Assistant's built-in Moen Flo integration. Reuses its authenticated client; no additional credentials are required.

## Installation

Add `https://github.com/B-Hartley/flo_alerts` as an Integration custom repository in HACS, or copy `custom_components/flo_alerts` into your configuration directory. Add `flo_alerts: {}` to `configuration.yaml` and restart Home Assistant. Keep the built-in Flo integration configured.

## Actions

In Developer Tools > Actions, run `flo_alerts.get_alerts` with empty data to retrieve outstanding warning and critical alerts. Specify `location_id` if multiple locations exist. After investigating the cause, run `flo_alerts.clear_alert` with the numeric `alarm_id` from the response. Alarm IDs identify types, not unique events; multiple events of the same type may be acknowledged. The action requests zero snooze seconds and does not explicitly change valve position or system mode. Check the returned `still_triggered` field. Do not automatically acknowledge uninvestigated alarms. If a write fails, retrieve alerts before retrying.

## Compatibility

Experimental, not yet live-tested. Depends on the built-in Flo integration runtime and private aioflo request method, which may change. The POST response and zero-snooze behaviour need live verification. No credentials or personal captures are included.

## Development

Run `python -m unittest discover -s tests` and `ruff check .` / `ruff format --check .`. See [Home Assistant development guidelines](https://developers.home-assistant.io/docs/development_guidelines/).
