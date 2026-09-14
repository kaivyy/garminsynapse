"""Unit tests for GarminExtractor's activity-list pagination.

Regression coverage for a bug where extract_all() hardcoded a single
`get_activities(start=0, limit=50)` call, silently capping every sync at
the 50 most-recent activities regardless of the requested `days` window or
how many activities actually exist in the account.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from garminsynapse.etl.extractor import GarminExtractor


def _activity(activity_id: int, start_time_local: str) -> dict:
    return {"activityId": activity_id, "activityName": f"Act {activity_id}", "startTimeLocal": start_time_local}


class TestParseActivityStart:
    def test_parses_valid_start_time_local(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        dt = extractor._parse_activity_start(_activity(1, "2026-01-02 03:04:05"))
        assert dt == datetime(2026, 1, 2, 3, 4, 5)

    def test_returns_none_for_missing_field(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        assert extractor._parse_activity_start({"activityId": 1}) is None

    def test_returns_none_for_unparseable_value(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        assert extractor._parse_activity_start({"startTimeLocal": "not-a-date"}) is None


class TestFetchActivitiesSince:
    def test_paginates_until_page_older_than_start_date(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        extractor._ACTIVITY_PAGE_SIZE = 2
        extractor._ACTIVITY_SAFETY_MAX_PAGES = 10

        page1 = [_activity(1, "2026-03-10 10:00:00"), _activity(2, "2026-03-09 10:00:00")]
        page2 = [_activity(3, "2026-03-08 10:00:00"), _activity(4, "2026-01-01 10:00:00")]
        # page2's oldest activity (2026-01-01) is before start_date, so pagination should stop here.
        page3 = [_activity(5, "2025-01-01 10:00:00"), _activity(6, "2024-01-01 10:00:00")]

        api = MagicMock()
        api.get_activities.side_effect = [page1, page2, page3]

        start_date = datetime(2026, 2, 1)
        result = extractor._fetch_activities_since(api, start_date)

        assert [a["activityId"] for a in result] == [1, 2, 3, 4]
        assert api.get_activities.call_count == 2

    def test_stops_on_short_last_page(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        extractor._ACTIVITY_PAGE_SIZE = 100
        extractor._ACTIVITY_SAFETY_MAX_PAGES = 10

        # Fewer results than the page size -> this is the last page, even though
        # every activity is more recent than start_date.
        short_page = [_activity(i, "2026-03-01 10:00:00") for i in range(5)]
        api = MagicMock()
        api.get_activities.side_effect = [short_page]

        result = extractor._fetch_activities_since(api, datetime(2020, 1, 1))

        assert len(result) == 5
        assert api.get_activities.call_count == 1

    def test_respects_safety_page_cap_to_avoid_unbounded_pagination(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        extractor._ACTIVITY_PAGE_SIZE = 2
        extractor._ACTIVITY_SAFETY_MAX_PAGES = 3

        # Every page is "full" and still newer than start_date, so without a
        # safety cap this would paginate forever.
        full_page = [_activity(1, "2026-03-10 10:00:00"), _activity(2, "2026-03-09 10:00:00")]
        api = MagicMock()
        api.get_activities.return_value = full_page

        result = extractor._fetch_activities_since(api, datetime(2000, 1, 1))

        assert api.get_activities.call_count == 3
        assert len(result) == 6

    def test_stops_immediately_on_empty_page(self):
        extractor = GarminExtractor.__new__(GarminExtractor)
        extractor._ACTIVITY_PAGE_SIZE = 50
        extractor._ACTIVITY_SAFETY_MAX_PAGES = 10

        api = MagicMock()
        api.get_activities.return_value = []

        result = extractor._fetch_activities_since(api, datetime(2020, 1, 1))

        assert result == []
        assert api.get_activities.call_count == 1


class TestExtractAllUsesPagination:
    def test_extract_all_saves_paginated_activities_not_hardcoded_fifty(self, tmp_path, monkeypatch):
        extractor = GarminExtractor(ingest_dir=tmp_path)
        monkeypatch.setattr(extractor.auth_mgr, "get_active_tokens", lambda *a, **k: {"access_token": "fake"})

        many_activities = [_activity(i, "2026-03-01 10:00:00") for i in range(120)]

        def fake_fetch_activities_since(self_api, api, start_date):
            return many_activities

        monkeypatch.setattr(GarminExtractor, "_fetch_activities_since", lambda self, api, start_date: many_activities)
        monkeypatch.setattr("garminsynapse.etl.extractor.GarminAPI", lambda *a, **k: MagicMock())

        extractor.extract_all(days=1)

        out_path = tmp_path / "activities_list.json"
        assert out_path.exists()
        import json
        saved = json.loads(out_path.read_text())
        assert len(saved) == 120
