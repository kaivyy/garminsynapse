import time
import pytest
from garminsynapse.core.throttler import Throttler, GarminRateLimitError


@pytest.fixture(autouse=True)
def reset_throttler():
    Throttler.reset()
    yield
    Throttler.reset()


def test_throttler_initial_state():
    assert not Throttler.is_rate_limited()
    assert Throttler.get_remaining_cooldown() == 0.0
    # ensure_not_rate_limited should not raise
    Throttler.ensure_not_rate_limited()


def test_throttler_mark_rate_limited():
    Throttler.mark_rate_limited(cooldown_seconds=5.0)
    assert Throttler.is_rate_limited()
    remaining = Throttler.get_remaining_cooldown()
    assert 0.0 < remaining <= 5.0
    
    with pytest.raises(GarminRateLimitError) as exc_info:
        Throttler.ensure_not_rate_limited()
    assert "Rate limited" in str(exc_info.value)


def test_throttler_cooldown_expiry():
    Throttler.mark_rate_limited(cooldown_seconds=0.1)
    assert Throttler.is_rate_limited()
    time.sleep(0.15)
    assert not Throttler.is_rate_limited()
    assert Throttler.get_remaining_cooldown() == 0.0
    Throttler.ensure_not_rate_limited()


def test_adaptive_sleep_duration(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    
    Throttler.adaptive_sleep(min_s=1.0, max_s=2.0)
    assert len(slept) == 1
    assert 1.0 <= slept[0] <= 2.0


def test_with_auto_retry_handles_429_and_marks_throttler(monkeypatch):
    from garminsynapse.core.api import with_auto_retry
    
    attempts = 0
    @with_auto_retry
    def mock_api_call():
        nonlocal attempts
        attempts += 1
        raise Exception("HTTP 429 Too Many Requests: Rate limit exceeded")
    
    with pytest.raises(Exception) as exc_info:
        mock_api_call()
    
    assert "429" in str(exc_info.value)
    assert Throttler.is_rate_limited()


def test_with_auto_retry_backs_off_on_transient_500(monkeypatch):
    from garminsynapse.core.api import with_auto_retry
    
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    
    attempts = 0
    @with_auto_retry
    def mock_transient_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("500 Internal Server Error")
        return {"status": "ok"}
    
    result = mock_transient_call()
    assert result == {"status": "ok"}
    assert attempts == 3
    assert len(slept) >= 2
    # Verify exponential backoff: second sleep should be greater than first
    assert slept[1] > slept[0]

