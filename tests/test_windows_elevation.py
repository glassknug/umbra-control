import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,Mock
import windows_elevation as elevation


class ElevationTests(unittest.TestCase):
    def test_frozen_restart_targets_itself_and_only_wait_flag(self):
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(Path('app with spaces/UmbraControl.exe').resolve())):
            executable,args,directory=elevation.restart_command()
            self.assertEqual(args,'--wait-for-pid '+str(os.getpid()))
            self.assertEqual(Path(executable).parent,Path(directory))

    def test_uac_denial_raises_without_claiming_success(self):
        shell=Mock();shell.ShellExecuteW.return_value=5
        with patch.object(elevation,'restart_command',return_value=('app.exe','args','folder')),patch.object(elevation.ctypes,'WinDLL',return_value=shell,create=True):
            with self.assertRaisesRegex(OSError,'cancelled'):elevation.request_restart()

    def test_handoff_wait_closes_handle_on_timeout(self):
        kernel=Mock();kernel.OpenProcess.return_value=123;kernel.WaitForSingleObject.return_value=258
        with patch.object(elevation.ctypes,'WinDLL',return_value=kernel,create=True):
            with self.assertRaisesRegex(OSError,'did not close'):elevation.wait_for_previous(['--wait-for-pid',str(os.getpid()+100)])
        kernel.CloseHandle.assert_called_once_with(123)

    def test_self_pid_rejected(self):
        with self.assertRaises(ValueError):elevation.wait_for_previous(['--wait-for-pid',str(os.getpid())])
