"""Unit tests for GarminAPI.download_activity_fit's ZIP-unwrapping behavior.

Garmin Connect's ActivityDownloadFormat.ORIGINAL sometimes returns a ZIP
archive containing a single ``<id>_ACTIVITY.fit`` member (observed for
activities recorded via the Garmin Connect mobile app) rather than raw FIT
bytes. download_activity_fit must transparently unwrap this so callers
always get raw FIT bytes.
"""
import io
import zipfile
from unittest.mock import MagicMock

from garminsynapse.core.api import GarminAPI


def _bare_api(garmin_instance=None) -> GarminAPI:
    api = GarminAPI.__new__(GarminAPI)
    api._garmin_instance = garmin_instance
    return api


def _zip_bytes(inner_name: str, inner_content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(inner_name, inner_content)
    return buf.getvalue()


class TestDownloadActivityFit:
    def test_returns_raw_bytes_unchanged_when_not_a_zip(self):
        mock_garmin = MagicMock()
        mock_garmin.download_activity.return_value = b"\x0e\x10\x8c\x00.FIT_RAW_BYTES"
        api = _bare_api(garmin_instance=mock_garmin)

        result = api.download_activity_fit(123)

        assert result == b"\x0e\x10\x8c\x00.FIT_RAW_BYTES"

    def test_unwraps_zip_containing_single_fit_member(self):
        inner = b"FAKEFITDATA"
        zipped = _zip_bytes("123_ACTIVITY.fit", inner)
        mock_garmin = MagicMock()
        mock_garmin.download_activity.return_value = zipped
        api = _bare_api(garmin_instance=mock_garmin)

        result = api.download_activity_fit(123)

        assert result == inner

    def test_unwraps_zip_picking_the_fit_member_among_others(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("readme.txt", b"not fit")
            z.writestr("123_ACTIVITY.fit", b"THE_REAL_FIT")
        mock_garmin = MagicMock()
        mock_garmin.download_activity.return_value = buf.getvalue()
        api = _bare_api(garmin_instance=mock_garmin)

        result = api.download_activity_fit(123)

        assert result == b"THE_REAL_FIT"

    def test_returns_empty_bytes_when_not_authenticated(self):
        api = _bare_api(garmin_instance=None)
        api.base_url = "https://connect.garmin.com"
        api.session = MagicMock()
        api.session.get.return_value = MagicMock(status_code=404, content=b"")

        result = api.download_activity_fit(123)

        assert result == b""
