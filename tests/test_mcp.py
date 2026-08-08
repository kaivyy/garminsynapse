"""Unit tests for MCP tools."""
from garminsynapse.mcp.tools import garmin_status

def test_garmin_status():
    result = garmin_status()
    assert isinstance(result, dict)
    assert result["status"] == "OK"
    assert "authenticated" in result
