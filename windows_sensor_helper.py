"""Read sensor values only; never call hardware control APIs."""
import json
import math
from pathlib import Path
import sys
import threading
import time


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
    try:
        if sys.platform != 'win32':raise RuntimeError('Windows sensor helper requires Windows')
        folder=Path(sys.argv[1]).resolve()
        if not (folder/'LibreHardwareMonitorLib.dll').is_file():raise RuntimeError('LibreHardwareMonitor library missing')
        sys.path.append(str(folder))
        from pythonnet import load
        load('netfx')
        import clr
        clr.AddReference(str(folder/'LibreHardwareMonitorLib.dll'))
        from LibreHardwareMonitor.Hardware import Computer
        computer=Computer()
        computer.IsCpuEnabled=True
        computer.IsGpuEnabled=True
        # Avoid unrelated controller/board probing in this first sensor preview.
        computer.Open()
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
            print(json.dumps(dict(sensors=sample),ensure_ascii=True,allow_nan=False),flush=True)
            done.wait(1)
        return 0
    except Exception as exc:
        print(json.dumps(dict(error=f'{type(exc).__name__}: {exc}')),flush=True)
        return 1
    finally:
        if computer is not None:
            try:computer.Close()
            except Exception:pass


if __name__=='__main__':raise SystemExit(main())
