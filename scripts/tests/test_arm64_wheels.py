import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_arm64_wheels import verify_wheel, require_native


def pe(machine):
    data = bytearray(128)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<H', data, 68, machine)
    return data


class WheelArchitectureTests(unittest.TestCase):
    def test_native_pe_and_pure_python_wheels(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp) / 'example-1.0-cp312-cp312-win_arm64.whl'
            with zipfile.ZipFile(native, 'w') as z:
                z.writestr('example/module.pyd', pe(0xaa64))
                z.writestr('example/runtime.dll', pe(0xaa64))
            verify_wheel(native)
            pure = Path(tmp) / 'example-1.0-py3-none-any.whl'
            with zipfile.ZipFile(pure, 'w') as z:
                z.writestr('example/__init__.py', '')
            verify_wheel(pure)

    def test_rejects_foreign_tag_or_embedded_foreign_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tag, machine in [('cp312-cp312-win_amd64', 0xaa64), ('cp312-cp312-win_arm64', 0x8664), ('py3-none-any', 0x8664)]:
                p = Path(tmp) / f'example-1.0-{tag}.whl'
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr('example/runtime.dll', pe(machine))
                with self.assertRaises(ValueError):
                    verify_wheel(p)

    def test_refuses_non_native_build_host(self):
        if sys.platform != 'win32':
            with self.assertRaisesRegex(RuntimeError, 'native Windows ARM64'):
                require_native()
