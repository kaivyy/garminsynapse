"""Unit tests for ETL extractor and processor."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from garminsynapse.etl.extractor import GarminExtractor
from garminsynapse.core.throttler import Throttler


def test_extractor_init(tmp_path):
    extractor = GarminExtractor(ingest_dir=tmp_path)
    assert extractor.ingest_dir == tmp_path


def test_extractor_pacing_invokes_throttler(tmp_path, monkeypatch):
    slept = []
    monkeypatch.setattr(Throttler, "adaptive_sleep", lambda min_s, max_s: slept.append((min_s, max_s)))
    
    extractor = GarminExtractor(ingest_dir=tmp_path, pacing_delay=1.0)
    api = MagicMock()
    api.get_sleep_data.return_value = {"sleep": "ok"}
    extractor._save_endpoint_json(api, "get_sleep_data", "2026-09-26", "2026-09-26_SLEEP.json")
    
    assert len(slept) == 1
    assert slept[0][0] > 0
