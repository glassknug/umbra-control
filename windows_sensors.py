"""Cached read-only LibreHardwareMonitor telemetry from an isolated process."""
import atexit
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

MAX_AGE = 5.0
MAX_LINE = 1024 * 1024


def config_path():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'UmbraControl' / 'sensor-directory.txt'


def library_directory():
    from windows_setup import bundled_library
    try:
        folder = Path(config_path().read_text(encoding='utf-8').strip())
        if (folder / 'LibreHardwareMonitorLib.dll').is_file():
            return folder
    except (OSError, ValueError):
        pass
    return bundled_library()


def decode_sample(text):
    from sensors import Sensor
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('Invalid sensor response')
    if 'error' in data:
        raise ValueError(str(data['error'])[:500])
    rows = data.get('sensors')
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('Invalid sensor list')
    sensors = []; seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid sensor record')
        identity, source, label, kind = (row.get(k) for k in ('id','source','label','kind'))
        if any(not isinstance(s,str) or not s or len(s)>512 or any(ord(c)<32 for c in s) for s in (identity,source,label)):
            raise ValueError('Invalid sensor identity')
        if not identity.startswith('/') or kind not in ('temperature','fan') or identity in seen:
            raise ValueError('Invalid or duplicate sensor')
        seen.add(identity)
        value = row.get('value')
        limits = (-20,130) if kind=='temperature' else (0,100000)
        if type(value) not in (int,float) or not math.isfinite(value) or not limits[0] <= value <= limits[1]:
            value = None
        # LHM may expose zero when a CPU register read is unavailable.
        if kind=='temperature' and identity.startswith(('/amdcpu/','/intelcpu/')) and value==0:
            value=None
        sensors.append(Sensor('lhm:'+identity,source,label,kind,value))
    return sensors


class SensorCache:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.sensors = []
        self.sample_time = None
        self.started_at = clock()
        self.error = 'Waiting for first sensor sample'
        self.diagnostics = {}

    def accept(self, text):
        sample = decode_sample(text)
        details=json.loads(text).get('diagnostics',{})
        allowed=('process_bits','elevated','pawnio_device_access','library_version','pawnio_installed','pawnio_version','amd_module_loaded','raw_cpu_values')
        if not isinstance(details,dict):details={}
        details={k:str(details[k])[:500] for k in allowed if k in details}
        with self.lock:
            self.sensors = sample
            self.sample_time = self.clock()
            self.error = '' if sample else 'No sensors reported; check sensor permissions and setup'
            self.diagnostics=details

    def fail(self, error):
        with self.lock:
            self.sample_time = None
            self.error = str(error)[:500]

    def snapshot(self):
        with self.lock:
            fresh = self.sample_time is not None and 0 <= self.clock()-self.sample_time < MAX_AGE
            return list(self.sensors) if fresh else [replace(s,value=None) for s in self.sensors]

    def status(self):
        with self.lock:
            if self.sample_time is None and self.error == 'Waiting for first sensor sample' and self.clock()-self.started_at >= MAX_AGE:
                return 'No sensor samples received. Run windows_diagnostics.py --sensors to inspect library/driver access.'
            if self.error:
                return self.error
            if self.sample_time is None or not 0 <= self.clock()-self.sample_time < MAX_AGE:
                return 'Sensor samples stale; active curve requests 100%'
            cpu=[s for s in self.sensors if s.key.startswith(('lhm:/amdcpu/','lhm:/intelcpu/')) and s.kind=='temperature']
            if cpu and all(s.value is None for s in cpu):
                return 'CPU access needs administrator permission. Use Restart as administrator.' if self.diagnostics.get('elevated')=='False' else 'CPU reading unavailable. Helper elevated='+self.diagnostics.get('elevated','unknown')+'; PawnIO module loaded='+self.diagnostics.get('amd_module_loaded','unknown')+'. Run sensor diagnostics for details.'
            return 'LibreHardwareMonitor · read-only samples · expires after 5 seconds'


def helper_command(folder):
    executable=Path(sys.executable)
    if getattr(sys,'frozen',False):
        helper=executable.parent/'sensor-helper'/'UmbraSensorHelper.exe'
        if not helper.is_file():raise OSError('Packaged sensor helper missing. Extract the entire application ZIP.')
        return [str(helper),str(folder)]
    if executable.name.lower()=='pythonw.exe':executable=executable.with_name('python.exe')
    return [str(executable),'-u',str(Path(__file__).with_name('windows_sensor_helper.py')),str(folder)]


class SensorService:
    def __init__(self, folder):
        self.cache = SensorCache()
        self.process = None
        self.thread = None
        self.folder = folder

    def start(self):
        try:
            self.process = subprocess.Popen(helper_command(self.folder),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.thread = threading.Thread(target=self._read,daemon=True)
            self.thread.start()
        except OSError as exc:
            self.cache.fail(exc)

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(MAX_LINE+1)
                if not line:
                    raise OSError('Sensor helper stopped; use Restart sensor reader after fixing setup')
                if len(line)>MAX_LINE:
                    raise ValueError('Sensor response too large')
                self.cache.accept(line.decode('utf-8'))
        except (OSError,ValueError,UnicodeError,RecursionError) as exc:
            self.cache.fail(exc)
        finally:
            # Stop a malformed or failed helper; never keep its last good value alive.
            if self.process.stdin and not self.process.stdin.closed:
                try:self.process.stdin.close()
                except OSError:pass

    def stop(self):
        p=self.process
        if p is None:return
        try:
            if p.stdin and not p.stdin.closed:p.stdin.close()
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.terminate();p.wait(timeout=2)
        except OSError:pass
        self.cache.fail('Sensor reader stopped')


_service = None
_paused = False
_guard = threading.Lock()


def read_sensors():
    global _service
    with _guard:
        if _paused:
            return _service.cache.snapshot() if _service else []
        if _service is None:
            folder = library_directory()
            if folder is None:return []
            _service = SensorService(folder);_service.start()
        return _service.cache.snapshot()


def status():
    if _paused:return 'Sensor reader stopped; active curve requests 100%'
    return _service.cache.status() if _service else 'Choose the official LibreHardwareMonitor folder to enable Windows temperatures'


def diagnostics():
    if _service is None:return {}
    with _service.cache.lock:return dict(_service.cache.diagnostics)


def restart(folder=None):
    global _service, _paused
    if folder is not None:
        folder=Path(folder).resolve()
        if not (folder/'LibreHardwareMonitorLib.dll').is_file():
            raise ValueError('Select the extracted folder containing LibreHardwareMonitorLib.dll and its dependencies')
        path=config_path();path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(str(folder),encoding='utf-8')
    stop()
    with _guard:
        _service=None
        _paused=False
    read_sensors()


def stop():
    global _paused
    with _guard:
        _paused=True
        if _service is not None:_service.stop()


atexit.register(stop)
