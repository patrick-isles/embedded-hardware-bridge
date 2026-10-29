#!/usr/bin/env python3
# ==============================================================================
# Test Suite: test_crc16_and_framing.py
# Purpose: Unit and Integration Tests for Embedded Hardware Bridge
# Target: CRC-16-CCITT integrity, packet framing, and Ohm's law calculations
# Author: Patrick Isles (https://github.com/patrick-isles)
# License: MIT
# ==============================================================================

import unittest
import struct

def crc16_ccitt(data: bytes, poly=0x1021, init=0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

SYNC_HEADER = bytes([0xAA, 0x55])
PAYLOAD_FORMAT = ">HHHhBBI"
PAYLOAD_LEN = struct.calcsize(PAYLOAD_FORMAT)

def pack_telemetry_frame(v_mv, i_ma, adc, temp_cdeg, gpio, faults, seq):
    payload = struct.pack(PAYLOAD_FORMAT, v_mv, i_ma, adc, temp_cdeg, gpio, faults, seq)
    crc = crc16_ccitt(payload)
    return SYNC_HEADER + bytes([PAYLOAD_LEN]) + payload + struct.pack(">H", crc)

class TestCRC16AndFraming(unittest.TestCase):

    def test_crc16_standard_vector(self):
        """Verify CCITT standard test vector: ASCII b'123456789' produces 0x29B1."""
        test_vector = b"123456789"
        expected_crc = 0x29B1
        self.assertEqual(crc16_ccitt(test_vector), expected_crc, "CRC-16-CCITT standard test vector failure")

    def test_frame_packing_and_length(self):
        """Verify 19-byte packet geometry: 2 SYNC + 1 LEN + 14 PAYLOAD + 2 CRC."""
        frame = pack_telemetry_frame(3300, 250, 2703, 2540, 0b00000001, 0, 1)
        self.assertEqual(len(frame), 19, "Frame size must be exactly 19 bytes")
        self.assertEqual(frame[0:2], SYNC_HEADER, "Frame must begin with 0xAA 0x55")
        self.assertEqual(frame[2], 14, "Payload length byte must be 14")

    def test_crc_detection_on_bit_flip(self):
        """Ensure any 1-bit or byte corruption triggers CRC validation failure."""
        valid_frame = pack_telemetry_frame(5000, 500, 4095, 3000, 0xFF, 0, 42)
        payload = valid_frame[3:3 + PAYLOAD_LEN]
        rx_crc = struct.unpack(">H", valid_frame[3 + PAYLOAD_LEN:3 + PAYLOAD_LEN + 2])[0]
        self.assertEqual(crc16_ccitt(payload), rx_crc, "Valid frame CRC must pass")

        # Corrupt single bit in payload
        corrupted_payload = bytearray(payload)
        corrupted_payload[4] ^= 0x01 # flip least significant bit
        corrupted_crc = crc16_ccitt(bytes(corrupted_payload))
        self.assertNotEqual(corrupted_crc, rx_crc, "Corrupted payload must not match original CRC")

    def test_ohms_law_and_power_computations(self):
        """Validate DC power (P=VI) and resistance (R=V/I) calculations."""
        # 5.0 V bus with 0.250 A load -> P = 1.25 W, R = 20.0 Ohms
        voltage_v = 5.000
        current_a = 0.250
        power_w = voltage_v * current_a
        resistance_ohms = voltage_v / current_a if current_a > 0.001 else 0.0

        self.assertAlmostEqual(power_w, 1.250, places=3)
        self.assertAlmostEqual(resistance_ohms, 20.000, places=3)

    def test_adc_quantization_resolution(self):
        """Validate 12-bit ADC quantization mapping (0-4095 corresponding to 0-5.0V)."""
        v_ref = 5.0
        resolution_steps = 4095
        lsb_voltage = v_ref / resolution_steps # ~1.22 mV per step

        # Test midpoint (2.5V approx code 2047)
        midpoint_code = 2048
        calculated_v = (midpoint_code / resolution_steps) * v_ref
        self.assertAlmostEqual(calculated_v, 2.5006, places=3)

    def test_stream_framing_resynchronization(self):
        """Test parser behavior when noise/garbage precedes a valid telemetry frame."""
        garbage = b"\x00\xFF\x12\x34\xAA\x00\xDE\xAD\xBE\xEF"
        valid_frame = pack_telemetry_frame(3300, 100, 2703, 2100, 0x05, 0, 99)
        stream_buffer = bytearray(garbage + valid_frame)

        # Search for SYNC_HEADER
        sync_idx = stream_buffer.find(SYNC_HEADER)
        self.assertNotEqual(sync_idx, -1, "Sync header must be discovered in stream")

        # Slice past garbage
        del stream_buffer[:sync_idx]
        self.assertEqual(stream_buffer[0:2], SYNC_HEADER)

        # Decode payload
        payload = bytes(stream_buffer[3:3 + PAYLOAD_LEN])
        rx_crc = struct.unpack(">H", stream_buffer[3 + PAYLOAD_LEN:3 + PAYLOAD_LEN + 2])[0]
        self.assertEqual(crc16_ccitt(payload), rx_crc, "Discovered frame must pass CRC check")

if __name__ == "__main__":
    unittest.main()
