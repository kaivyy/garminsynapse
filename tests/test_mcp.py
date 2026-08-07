from garminsynapse.mcp.tools import garmin_status

def test_garmin_status():
    assert garmin_status() == "OK"
