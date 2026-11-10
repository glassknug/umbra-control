from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from windows_sensors import helper_command


class WindowsPackageTests(unittest.TestCase):
    def test_frozen_app_starts_dedicated_helper_not_itself(self):
        with tempfile.TemporaryDirectory(prefix='umbra package ') as folder:
            root=Path(folder)
            helper=root/'sensor-helper/UmbraSensorHelper.exe'
            helper.parent.mkdir();helper.touch()
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(root/'UmbraControl.exe')):
                self.assertEqual(helper_command('sensor library'),[str(helper),'sensor library'])

    def test_incomplete_extraction_fails_without_gui_recursion(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(Path(folder)/'UmbraControl.exe')):
            with self.assertRaisesRegex(OSError,'Extract the entire'):helper_command('library')

    def test_source_pythonw_still_uses_console_python_with_pipes(self):
        with patch.object(sys,'frozen',False,create=True),patch.object(sys,'executable','C:/app/.venv/Scripts/pythonw.exe'):
            command=helper_command('library')
            self.assertTrue(command[0].endswith('python.exe'))
            self.assertEqual(command[1],'-u')
            self.assertTrue(command[2].endswith('windows_sensor_helper.py'))
