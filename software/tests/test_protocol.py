"""Unit tests for the bus protocol:  python3 -m unittest discover software/tests"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import picase_bus as pb  # noqa: E402


class FramingTests(unittest.TestCase):
    def test_round_trip(self):
        raw = pb.make(3, 0, pb.STATS_REQ, 42, {"x": 1})
        (f,) = pb.Decoder().feed(raw)
        self.assertEqual((f.dst, f.src, f.type, f.seq, f.data), (3, 0, pb.STATS_REQ, 42, {"x": 1}))

    def test_crc_known_value(self):
        self.assertEqual(pb.crc16_ccitt(b"123456789"), 0x29B1)   # CCITT-FALSE check value

    def test_byte_at_a_time(self):
        raw = pb.make(1, 0, pb.PING, 7) + pb.make(2, 0, pb.PING, 8)
        d, out = pb.Decoder(), []
        for b in raw:
            out += d.feed(bytes([b]))
        self.assertEqual([f.seq for f in out], [7, 8])

    def test_resync_after_noise_and_corruption(self):
        good = pb.make(5, 0, pb.PING, 1, {"hello": "world"})
        bad = bytearray(pb.make(5, 0, pb.PING, 2))
        bad[-1] ^= 0xFF                                  # break the CRC
        noise = bytes(random.Random(1).randrange(256) for _ in range(200))
        d = pb.Decoder()
        frames = d.feed(noise + bytes(bad) + good + b"\x7e\x7e" + good)
        self.assertEqual([f.seq for f in frames], [1, 1])
        self.assertGreater(d.bad_frames, 0)

    def test_payload_limit(self):
        with self.assertRaises(ValueError):
            pb.encode(pb.Frame(1, 0, pb.PONG, 0, b"x" * (pb.MAX_PAYLOAD + 1)))


if __name__ == "__main__":
    unittest.main()
