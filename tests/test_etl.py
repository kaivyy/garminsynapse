import pytest
from garminsynapse.etl.extractor import GarminExtractor
from datetime import date

def test_extractor_init():
    extractor = GarminExtractor(date(2023, 1, 1), date(2023, 1, 2), "/tmp")
    assert extractor.start_date == date(2023, 1, 1)
