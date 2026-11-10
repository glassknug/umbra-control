"""Explicit UAC restart with a process handoff before opening USB or session lock."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys


def restart_command():
    executable=Path(sys.executable).resolve()
    arguments=[]
    if not getattr(sys,'frozen',False):
        executable=executable.with_name('pythonw.exe')
        arguments.append(str(Path(__file__).with_name('windows_launch.pyw').resolve()))
    arguments.extend(['--wait-for-pid',str(os.getpid())])
    return str(executable),subprocess.list2cmdline(arguments),str(executable.parent)


def request_restart():
    executable,arguments,directory=restart_command()
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.ShellExecuteW.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_int]
    shell.ShellExecuteW.restype=ctypes.c_ssize_t
    result=shell.ShellExecuteW(None,'runas',executable,arguments,directory,1)
    if result<=32:
        raise OSError('Administrator restart was cancelled or could not start. Umbra Control is still running.')


def wait_for_previous(arguments):
    if not arguments:return
    if len(arguments)!=2 or arguments[0]!='--wait-for-pid' or not arguments[1].isdigit():
        return
    pid=int(arguments[1])
    if pid<=0 or pid==os.getpid():raise ValueError('Invalid restart process')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x00100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return # previous process already exited
        raise OSError('Could not wait for previous Umbra process. Quit it and launch again.')
    try:
        if kernel.WaitForSingleObject(handle,60000)!=0:
            raise OSError('Previous Umbra process did not close. Quit it and launch again.')
    finally:kernel.CloseHandle(handle)
