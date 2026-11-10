import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import windows_startup as win


def profile(duty=50):
    return dict(name='Quiet',sensor='lhm:/amdcpu/0/temperature/2',shortcut='1',points=[[35,duty],[80,100]])


class WindowsStartupTests(unittest.TestCase):
    def setup_context(self,root):
        return patch.object(win,'config_path',return_value=root/'startup.json')

    def test_saved_snapshot_enable_update_and_disable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);exe=root/'UmbraControl.exe';exe.touch()
            with self.setup_context(root),patch.object(win,'is_elevated',return_value=True),patch.object(win,'launch_command',return_value=(exe,['--autostart'],root)),patch('windows_sensors.library_directory',return_value=root),patch.object(win,'_task',return_value=True) as task:
                win.configure(profile())
                self.assertEqual(win.load()['points'][0][1],50)
                win.configure(profile(60));self.assertEqual(win.load()['points'][0][1],60)
                win.configure(None)
                self.assertFalse((root/'startup.json').exists())
                self.assertEqual(task.call_args.args[0],'disable')

    def test_registration_failure_rolls_back_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);exe=root/'UmbraControl.exe';exe.touch()
            for old in (None,b'{"old":"exact bytes"}'):
                path=root/'startup.json'
                if old is None:path.unlink(missing_ok=True)
                else:path.write_bytes(old)
                with self.setup_context(root),patch.object(win,'is_elevated',return_value=True),patch.object(win,'launch_command',return_value=(exe,['--autostart'],root)),patch('windows_sensors.library_directory',return_value=root),patch.object(win,'_task',side_effect=OSError('denied')):
                    with self.assertRaises(OSError):win.configure(profile())
                self.assertEqual(path.read_bytes() if path.exists() else None,old)

    def test_no_privilege_or_low_curve_never_registers(self):
        with patch.object(win,'_task') as task:
            with patch.object(win,'is_elevated',return_value=False),self.assertRaises(ValueError):win.configure(profile())
            with patch.object(win,'is_elevated',return_value=True),self.assertRaises(ValueError):win.configure(profile(49))
            task.assert_not_called()

    def test_task_data_not_interpolated_into_script(self):
        result=Mock(returncode=0,stdout=b'{"exists":true}',stderr=b'')
        with patch.dict(os.environ,SystemRoot='C:/Windows'),patch.object(win.subprocess,'run',return_value=result) as run:
            win._task('enable',(Path("C:/User's app/UmbraControl.exe"),['--autostart'],Path("C:/User's app")))
            script=base64.b64decode(run.call_args.args[0][-1]).decode('utf-16le')
            self.assertNotIn("User's app",script)
            self.assertIn('-LogonType Interactive -RunLevel Highest',script)
            self.assertIn("GetCurrent().User.Value",script)
            self.assertIn("'PT30S'",script)
            self.assertNotIn('-Password',script)
            self.assertEqual(run.call_args.kwargs['env']['UMBRA_TASK_ARGS'],'--autostart')

    def test_frozen_launch_has_no_python_script(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(Path(folder)/'UmbraControl.exe')):
            exe,args,cwd=win.launch_command()
            self.assertEqual(args,['--autostart'])
            self.assertEqual(exe.name,'UmbraControl.exe')

    def test_disabled_or_missing_task_does_not_load_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'startup.json').write_text(json.dumps(profile()))
            with self.setup_context(root),patch.object(win,'_task',return_value=False):self.assertIsNone(win.load())
