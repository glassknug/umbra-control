import base64
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import windows_shortcut


class WindowsShortcutTests(unittest.TestCase):
    def test_paths_are_data_not_powershell_code(self):
        with tempfile.TemporaryDirectory(prefix="umbra's app ") as folder:
            root=Path(folder)
            for name in ('.venv/Scripts/pythonw.exe','windows_launch.pyw','umbra-icon.ico'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            with patch.object(sys,'platform','win32'),patch.dict(os.environ,SystemRoot='C:/Windows'),patch('windows_shortcut.subprocess.run',return_value=Mock(returncode=0)) as run:
                windows_shortcut.create(root)
            args,kwargs=run.call_args
            command=args[0]
            script=base64.b64decode(command[-1]).decode('utf-16le')
            self.assertNotIn(str(root),script)
            self.assertEqual(kwargs['env']['UMBRA_SHORTCUT_ROOT'],str(root.resolve()))
            self.assertIn('windows_launch.pyw',kwargs['env']['UMBRA_SHORTCUT_ARGS'])
            self.assertNotIn('shell',kwargs)

    def test_incomplete_setup_does_not_create_shortcut(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(sys,'platform','win32'),patch('windows_shortcut.subprocess.run') as run:
            with self.assertRaises(OSError):windows_shortcut.create(folder)
            run.assert_not_called()
