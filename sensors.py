"""Read-only Linux hwmon telemetry. No assumptions about hub port mapping."""
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class Sensor:
    key: str
    source: str
    label: str
    kind: str
    value: float | None


def _read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return fallback


def read_sensors(root: Path | None = None) -> list[Sensor]:
    if root is None and sys.platform == 'win32':
        from windows_sensors import read_sensors as windows_read
        return windows_read()
    root = root or Path('/sys/class/hwmon')
    sensors = []
    for device in sorted(root.glob("hwmon*")):
        source = _read(device / "name", device.name)
        for prefix, kind, scale in (("temp", "temperature", 1000), ("fan", "fan", 1)):
            for path in sorted(device.glob(f"{prefix}[0-9]*_input")):
                stem = path.name.removesuffix("_input")
                label = _read(device / f"{stem}_label", stem) or stem
                try:
                    value = int(path.read_text().strip()) / scale
                    if _read(device / f"{stem}_fault") == "1":
                        value = None
                except (OSError, ValueError):
                    value = None
                sensors.append(Sensor(str(path), source, label, kind, value))
    return sensors


def cpu_temperature(sensors):
    """Prefer the CPU control/package reading; never substitute a GPU sensor."""
    for source, label in (("k10temp", "Tctl"), ("k10temp", "Tdie"),
                          ("coretemp", "Package id 0"), ("coretemp", "Package")):
        matches = [s for s in sensors if s.kind == "temperature" and
                   s.source == source and s.label == label]
        if len(matches) == 1:
            return matches[0]
    for label in ('Core (Tctl/Tdie)','Core (Tctl)','CPU Package','Core (Tdie)'):
        matches=[s for s in sensors if s.kind=='temperature' and s.key.startswith(('lhm:/amdcpu/','lhm:/intelcpu/')) and s.label==label]
        if len(matches)==1:return matches[0]
    return None

