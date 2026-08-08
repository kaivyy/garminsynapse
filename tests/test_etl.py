"""Unit tests for ETL extractor and processor."""
import pytest
from pathlib import Path
from garminsynapse.etl.extractor import GarminExtractor

def test_extractor_init(tmp_path):
    extractor = GarminExtractor(ingest_dir=tmp_path)
    assert extractor.ingest_dir == tmp_path
