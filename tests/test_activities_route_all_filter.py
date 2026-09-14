"""Regression test for GET /api/v1/activities silently capping the "All"
(no date filter) view at limit=100, even when the local database contains
many more activities. This is the second half of the "All only shows 50/100
activities" bug: the first half (extractor hardcoding a 50-activity sync
cap) is covered by tests/test_extractor_activity_pagination.py.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from garminsynapse.web.app import app
from garminsynapse.db.schema import Activity

client = TestClient(app)


def _make_activity(idx: int, days_ago: int) -> Activity:
    return Activity(
        activity_id=1000 + idx,
        user_id=1,
        activity_name=f"Activity {idx}",
        activity_type_key="hiking",
        start_ts=datetime.utcnow() - timedelta(days=days_ago),
        duration=1000.0,
        distance=1000.0,
    )


class _FakeQuery:
    def __init__(self, records):
        self._records = records

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return _FakeQuery(self._records[:n])

    def all(self):
        return self._records


class TestActivitiesRouteNoDateFilter:
    def test_returns_more_than_one_hundred_when_no_limit_specified(self):
        records = [_make_activity(i, i) for i in range(300)]

        with patch("garminsynapse.web.routes.DualAuthManager") as MockAuth, \
             patch("garminsynapse.web.routes.DatabaseManager") as MockDb:
            MockAuth.return_value.get_active_tokens.return_value = {"access_token": "fake"}
            mock_session = MagicMock()
            mock_session.query.return_value = _FakeQuery(records)
            MockDb.return_value.get_session.return_value = mock_session

            response = client.get("/api/v1/activities")

        assert response.status_code == 200
        assert len(response.json()) == 300

    def test_explicit_limit_still_respected(self):
        records = [_make_activity(i, i) for i in range(300)]

        with patch("garminsynapse.web.routes.DualAuthManager") as MockAuth, \
             patch("garminsynapse.web.routes.DatabaseManager") as MockDb:
            MockAuth.return_value.get_active_tokens.return_value = {"access_token": "fake"}
            mock_session = MagicMock()
            mock_session.query.return_value = _FakeQuery(records)
            MockDb.return_value.get_session.return_value = mock_session

            response = client.get("/api/v1/activities?limit=25")

        assert response.status_code == 200
        assert len(response.json()) == 25
