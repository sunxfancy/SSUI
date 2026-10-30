import struct
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_native_binaries import pe_machine

class PETest(unittest.TestCase):
    def test_reads_machine_without_trusting_filename(self):
        for machine in (0xaa64, 0x8664):
            data = bytearray(128)
            data[:2] = b'MZ'
            struct.pack_into('<I', data, 0x3c, 64)
            data[64:68] = b'PE\0\0'
            struct.pack_into('<H', data, 68, machine)
            self.assertEqual(pe_machine(data), machine)
    def test_rejects_truncated_or_invalid_headers(self):
        for data in (b'', b'MZ', bytes(128), b'MZ'+bytes(126)):
            with self.assertRaises(ValueError):
                pe_machine(data)
