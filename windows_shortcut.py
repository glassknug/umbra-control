"""Create an icon-bearing shortcut on the current user's actual Desktop folder."""
import base64
import os
from pathlib import Path
import subprocess
import sys

SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$root = $env:UMBRA_SHORTCUT_ROOT
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { throw 'Desktop folder unavailable' }
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $desktop 'Umbra Control.lnk'))
$link.TargetPath = $env:UMBRA_SHORTCUT_TARGET
$link.Arguments = $env:UMBRA_SHORTCUT_ARGS
$link.WorkingDirectory = $root
$link.IconLocation = $env:UMBRA_SHORTCUT_ICON + ',0'
$link.Description = 'Umbra Control for Windows'
$link.Save()
'''


def create(root=None):
    if sys.platform != 'win32':raise OSError('Windows shortcut creation requires Windows')
    root=Path(root or (Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent)).resolve()
    packaged=(root/'UmbraControl.exe').is_file()
    required=(root/'UmbraControl.exe',) if packaged else (root/'.venv/Scripts/pythonw.exe',root/'windows_launch.pyw',root/'umbra-icon.ico')
    for path in required:
        if not path.is_file():raise OSError(f'Missing shortcut target: {path}')
    environment=os.environ.copy()
    environment['UMBRA_SHORTCUT_ROOT']=str(root)
    environment['UMBRA_SHORTCUT_TARGET']=str(root/'UmbraControl.exe' if packaged else root/'.venv/Scripts/pythonw.exe')
    environment['UMBRA_SHORTCUT_ICON']=str(root/'UmbraControl.exe' if packaged else root/'umbra-icon.ico')
    environment['UMBRA_SHORTCUT_ARGS']='' if packaged else subprocess.list2cmdline([str(root/'windows_launch.pyw')])
    executable=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    encoded=base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')
    result=subprocess.run([str(executable),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        env=environment,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise OSError('Could not create Desktop shortcut. You can still use start_windows.cmd.')


if __name__=='__main__':
    try:
        create();print('Umbra Control desktop shortcut created.')
    except (OSError,subprocess.SubprocessError) as exc:
        print(str(exc));raise SystemExit(1)
