"""FIT Binary File Encoder for Garmin upload (e.g. Weight Scale readings)."""
import struct
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FitEncoder:
    """Low-level binary FIT file generator."""

    @staticmethod
    def calc_crc(data: bytes) -> int:
        """Calculate 16-bit FIT CRC checksum."""
        crc_table = [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400
        ]
        crc = 0
        for byte in data:
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) ^ tmp ^ crc_table[byte & 0xF]
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) ^ tmp ^ crc_table[(byte >> 4) & 0xF]
        return crc & 0xFFFF

    @classmethod
    def encode_weight(cls, weight_kg: float, timestamp_sec: int) -> bytes:
        """Encode weight scale reading into binary FIT file format."""
        header = struct.pack("<BBHI4s", 14, 0x20, 0, 0, b".FIT")
        body = struct.pack("<I", timestamp_sec) + struct.pack("<H", int(weight_kg * 100))
        crc = cls.calc_crc(header + body)
        return header + body + struct.pack("<H", crc)
