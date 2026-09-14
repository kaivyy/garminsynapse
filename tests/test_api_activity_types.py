"""Unit tests for GarminAPI activity-type helper methods."""
from unittest.mock import MagicMock

import pytest

from garminsynapse.core.api import GarminAPI


def _bare_api(garmin_instance=None) -> GarminAPI:
    """Construct a GarminAPI instance without running the real __init__ (which
    would attempt to load cached credentials / hit the network)."""
    api = GarminAPI.__new__(GarminAPI)
    api._garmin_instance = garmin_instance
    return api


class TestGetActivityTypes:
    def test_returns_empty_list_when_not_authenticated(self):
        api = _bare_api(garmin_instance=None)
        assert api.get_activity_types() == []

    def test_delegates_to_garmin_instance(self):
        mock_garmin = MagicMock()
        mock_garmin.get_activity_types.return_value = [{"typeKey": "hiking"}]
        api = _bare_api(garmin_instance=mock_garmin)
        assert api.get_activity_types() == [{"typeKey": "hiking"}]


class TestResolveActivityType:
    def test_finds_matching_type_key(self):
        mock_garmin = MagicMock()
        mock_garmin.get_activity_types.return_value = [
            {"typeId": 9, "typeKey": "hiking", "parentTypeId": 17},
            {"typeId": 1, "typeKey": "running", "parentTypeId": 17},
        ]
        api = _bare_api(garmin_instance=mock_garmin)
        result = api.resolve_activity_type("running")
        assert result["typeId"] == 1

    def test_raises_for_unknown_type_key(self):
        mock_garmin = MagicMock()
        mock_garmin.get_activity_types.return_value = [{"typeId": 9, "typeKey": "hiking", "parentTypeId": 17}]
        api = _bare_api(garmin_instance=mock_garmin)
        with pytest.raises(ValueError):
            api.resolve_activity_type("underwater_basket_weaving")


class TestChangeActivityType:
    def test_resolves_and_calls_set_activity_type(self):
        mock_garmin = MagicMock()
        mock_garmin.get_activity_types.return_value = [{"typeId": 9, "typeKey": "hiking", "parentTypeId": 17}]
        mock_garmin.set_activity_type.return_value = {"activityId": 123}
        api = _bare_api(garmin_instance=mock_garmin)

        result = api.change_activity_type(123, "hiking")

        mock_garmin.set_activity_type.assert_called_once_with(123, 9, "hiking", 17)
        assert result == {"activityId": 123}

    def test_raises_when_not_authenticated(self):
        api = _bare_api(garmin_instance=None)
        with pytest.raises(RuntimeError):
            api.change_activity_type(123, "hiking")
