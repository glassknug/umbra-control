import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import sys
import windows_dependencies as deps
from windows_setup import bundled_library


class WindowsSetupTests(unittest.TestCase):
    def test_frozen_sensor_library_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            lib=folder/'LibreHardwareMonitor';lib.mkdir();(lib/'LibreHardwareMonitorLib.dll').touch()
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(folder/'UmbraControl.exe')):
                self.assertEqual(bundled_library(),lib)
            with patch.object(sys,'frozen',False,create=True):self.assertIsNone(bundled_library())

    def test_wrong_dependency_hash_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(deps.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(RuntimeError,'checksum'):deps.install_sensor_bundle(temporary)
            self.assertEqual(list(Path(temporary).iterdir()),[])

    def test_archive_escape_rejected(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:archive.writestr('../escape.dll',b'x')
        raw=data.getvalue()
        with tempfile.TemporaryDirectory() as temporary,patch.object(deps,'SHA256',deps.hashlib.sha256(raw).hexdigest()),patch.object(deps.urllib.request,'urlopen',return_value=io.BytesIO(raw)):
            with self.assertRaisesRegex(ValueError,'Unsafe'):deps.install_sensor_bundle(temporary)
