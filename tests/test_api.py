"""Test alert endpoint behavior without a live account."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location(
    "flo_api", Path(__file__).parents[1] / "custom_components/flo_alerts/api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class TestAlerts(unittest.IsolatedAsyncioTestCase):
    """Test safe acknowledgement and response validation."""

    async def test_acknowledge(self):
        """Use the numeric alarm type and request no snooze."""
        client = AsyncMock()
        item = {
            "id": "event",
            "locationId": "loc",
            "status": "triggered",
            "alarm": {"id": 73, "severity": "critical"},
        }
        client._request.side_effect = [
            {"items": [item], "total": 1}, {}, {"items": [], "total": 0}
        ]
        self.assertEqual(await api.acknowledge(client, "loc", 73), [])
        self.assertEqual(
            client._request.call_args_list[1].kwargs["json"],
            {"locationId": "loc", "alarmIds": [73], "snoozeSeconds": 0},
        )

    async def test_missing_alarm(self):
        """Do not write if the alarm is no longer outstanding."""
        client = AsyncMock()
        client._request.return_value = {"items": [], "total": 0}
        with self.assertRaises(ValueError):
            await api.acknowledge(client, "loc", 73)
        self.assertEqual(client._request.call_count, 1)
