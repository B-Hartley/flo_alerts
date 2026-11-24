"""Additional Flo API endpoints."""

from typing import Any

BASE = "https://api-gw.meetflo.com/api/v2/alerts"


async def active_alerts(client: Any, location_id: str) -> list[dict[str, Any]]:
    """Retrieve all outstanding warning and critical alerts."""
    result = []
    seen = set()
    for page in range(1, 101):
        data = await client._request(
            "get", BASE, params=[
                ("isInternalAlarm", "false"),
                ("locationId", location_id),
                ("status", "triggered"),
                ("severity", "warning"),
                ("severity", "critical"),
                ("page", str(page)),
                ("size", "100"),
            ],
        )
        items = data["items"]
        total = data["total"]
        if not isinstance(items, list) or type(total) is not int or total < 0:
            raise ValueError("Invalid alert response")
        for item in items:
            alarm = item["alarm"]
            if (
                item["locationId"] != location_id
                or item["status"] != "triggered"
                or type(alarm["id"]) is not int
                or alarm["severity"] not in ("warning", "critical")
                or item["id"] in seen
            ):
                raise ValueError("Unexpected alert response")
            seen.add(item["id"])
            result.append({
                "event_id": item["id"],
                "alarm_id": alarm["id"],
                "severity": alarm["severity"],
                "title": item.get("displayTitle"),
                "message": item.get("displayMessage"),
                "created_at": item.get("createAt"),
            })
        if len(result) == total:
            return result
        if not items or len(result) > total:
            raise ValueError("Inconsistent alert pagination")
    raise ValueError("Alert pagination limit exceeded")


async def acknowledge(client: Any, location_id: str, alarm_id: int) -> list[dict]:
    """Acknowledge one currently outstanding alarm type."""
    before = await active_alerts(client, location_id)
    if alarm_id not in {alert["alarm_id"] for alert in before}:
        raise ValueError("Alarm type is not currently outstanding")
    await client._request(
        "post", BASE + "/action",
        json={"locationId": location_id, "alarmIds": [alarm_id], "snoozeSeconds": 0},
    )
    return await active_alerts(client, location_id)
