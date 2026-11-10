"""Read sensor values only; never call hardware control APIs."""
import json
import math
import os
from pathlib import Path
import sys
import threading
import time


def process_access():
    """Inspect this helper's actual token and PawnIO access without sending IOCTLs."""
    import ctypes
    from ctypes import wintypes
    result={'process_bits':str(ctypes.sizeof(ctypes.c_void_p)*8),
            'elevated':str(bool(ctypes.windll.shell32.IsUserAnAdmin()))}
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype=wintypes.HANDLE
    close=kernel.CloseHandle
    close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
    handle=create(r'\\?\GLOBALROOT\Device\PawnIO',0xC0000000,3,None,3,0,None)
    if handle in (None,ctypes.c_void_p(-1).value):
        result['pawnio_device_access']='failed; Win32 error '+str(ctypes.get_last_error())
    else:
        close(handle);result['pawnio_device_access']='opened successfully (no IOCTL sent)'
    return result


def module_status(hardware):
    """Best-effort read-only inspection of the AMD module in the supported LHM build."""
    try:
        from System.Reflection import BindingFlags
        flags=BindingFlags.Instance | BindingFlags.NonPublic
        field=hardware.GetType().GetField('_pawnModule',flags)
        if field is None:return 'not exposed by this hardware type'
        module=field.GetValue(hardware)
        field=module.GetType().GetField('_pawnIo',flags)
        if field is None:return 'not exposed by this library version'
        return str(bool(field.GetValue(module).IsLoaded))
    except Exception as exc:
        return 'inspection unavailable: '+type(exc).__name__


def collect(hardware):
    hardware.Update()
    result=[]
    for sensor in hardware.Sensors:
        kind={'Temperature':'temperature','Fan':'fan'}.get(str(sensor.SensorType))
        if kind is None:continue
        value=float(sensor.Value) if sensor.Value is not None else None
        if value is not None and not math.isfinite(value):value=None
        result.append(dict(id=str(sensor.Identifier),source=str(hardware.Identifier),
                           label=str(sensor.Name),kind=kind,value=value))
    for child in hardware.SubHardware:result.extend(collect(child))
    return result


def main():
    computer=None
    dll_directory=None
    try:
        if sys.platform != 'win32':raise RuntimeError('Windows sensor helper requires Windows')
        folder=Path(sys.argv[1]).resolve()
        if not (folder/'LibreHardwareMonitorLib.dll').is_file():raise RuntimeError('LibreHardwareMonitor library missing')
        os.chdir(folder)
        sys.path.insert(0,str(folder))
        dll_directory=os.add_dll_directory(str(folder))
        from pythonnet import load
        load('netfx')
        import clr
        clr.AddReference(str(folder/'LibreHardwareMonitorLib.dll'))
        from LibreHardwareMonitor.Hardware import Computer
        from LibreHardwareMonitor.PawnIo import PawnIo
        diagnostics=process_access()
        diagnostics['library_version']=str(clr.GetClrType(Computer).Assembly.GetName().Version)
        diagnostics['pawnio_installed']=str(bool(PawnIo.IsInstalled))
        diagnostics['pawnio_version']=str(PawnIo.Version)
        computer=Computer()
        computer.IsCpuEnabled=True
        computer.IsGpuEnabled=True
        # Avoid unrelated controller/board probing in this first sensor preview.
        computer.Open()
        for h in computer.Hardware:
            if str(h.Identifier).startswith('/amdcpu/'):
                diagnostics['amd_module_loaded']=module_status(h)
        done=threading.Event()
        def watch_parent():
            sys.stdin.buffer.read(1)
            done.set()
        threading.Thread(target=watch_parent,daemon=True).start()
        while not done.is_set():
            sample=[]
            began=time.monotonic()
            for h in computer.Hardware:sample.extend(collect(h))
            if time.monotonic()-began >= 5:
                raise RuntimeError('Hardware sensor update took too long; sample discarded')
            diagnostics['raw_cpu_values']='; '.join(f"{s['id']}={s['value']}" for s in sample if s['id'].startswith(('/amdcpu/','/intelcpu/')) and s['kind']=='temperature')[:500]
            print(json.dumps(dict(sensors=sample,diagnostics=diagnostics),ensure_ascii=True,allow_nan=False),flush=True)
            done.wait(1)
        return 0
    except Exception as exc:
        print(json.dumps(dict(error=f'{type(exc).__name__}: {exc}')),flush=True)
        return 1
    finally:
        if computer is not None:
            try:computer.Close()
            except Exception:pass
        if dll_directory is not None:dll_directory.close()


if __name__=='__main__':raise SystemExit(main())
