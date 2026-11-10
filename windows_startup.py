"""Opt-in elevated interactive login task for the current Windows user only."""
import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

from config_transfer import atomic_write
from fan_curves import validate_profile

SCRIPT=r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$name = 'UmbraControl-' + $sid
$existing = Get-ScheduledTask -TaskPath '\' -TaskName $name -ErrorAction SilentlyContinue
switch ($env:UMBRA_TASK_OPERATION) {
  'query' {
    @{exists=([bool]$existing -and $existing.State -ne 'Disabled')} | ConvertTo-Json -Compress
  }
  'disable' {
    if ($existing) { Unregister-ScheduledTask -TaskPath '\' -TaskName $name -Confirm:$false }
  }
  'enable' {
    $action = New-ScheduledTaskAction -Execute $env:UMBRA_TASK_EXE -Argument $env:UMBRA_TASK_ARGS -WorkingDirectory $env:UMBRA_TASK_DIR
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $sid
    $trigger.Delay = 'PT30S'
    $principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskPath '\' -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Start Umbra Control minimized with the saved fan curve after this user logs in.' -Force | Out-Null
  }
  default { throw 'Unknown Umbra task operation' }
}
'''


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'umbra-control/startup.json'


def launch_command():
    executable=Path(sys.executable).resolve()
    if getattr(sys,'frozen',False):
        return executable,['--autostart'],executable.parent
    launcher=Path(__file__).with_name('windows_launch.pyw').resolve()
    windowed=executable.with_name('pythonw.exe')
    if windowed.is_file():executable=windowed
    return executable,[str(launcher),'--autostart'],launcher.parent


def _task(operation,launch=None):
    if operation not in ('query','enable','disable'):raise ValueError('Invalid task operation')
    environment=os.environ.copy();environment['UMBRA_TASK_OPERATION']=operation
    if launch:
        executable,arguments,directory=launch
        environment.update(UMBRA_TASK_EXE=str(executable),UMBRA_TASK_ARGS=subprocess.list2cmdline(arguments),UMBRA_TASK_DIR=str(directory))
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')],
            env=environment,capture_output=True,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.SubprocessError as exc:
        raise OSError('Windows startup task operation timed out or failed') from exc
    if result.returncode:
        raise OSError('Could not '+operation+' Windows login startup. Run Umbra as administrator and retry. '+result.stderr.decode('utf-8',errors='replace')[-600:])
    if operation=='query':
        return bool(json.loads(result.stdout.decode('utf-8-sig'))['exists'])


def is_elevated():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def load():
    path=config_path()
    if not path.is_file() or not _task('query'):return None
    return validate_profile(json.loads(path.read_text(encoding='utf-8')))


def configure(profile):
    if not is_elevated():raise ValueError('Run Umbra as administrator to change Windows login startup')
    path=config_path()
    if profile is None:
        _task('disable');path.unlink(missing_ok=True);return
    profile=validate_profile(profile)
    if not profile['sensor'].startswith('lhm:/') or any(p[1]<50 for p in profile['points']):
        raise ValueError('Windows startup needs a local temperature sensor and 50–100% curve')
    from windows_sensors import library_directory
    if library_directory() is None:raise ValueError('Choose the sensor library folder before enabling login startup')
    launch=launch_command()
    if not launch[0].is_file():raise ValueError('Startup executable is missing')
    previous=path.read_bytes() if path.exists() else None
    atomic_write(path,(json.dumps(profile,indent=2)+'\n').encode('utf-8'))
    try:_task('enable',launch)
    except (OSError,subprocess.SubprocessError,ValueError):
        if previous is None:path.unlink(missing_ok=True)
        else:atomic_write(path,previous)
        raise
