"""Fan curve math and atomic per-user profile storage. No hardware writes."""
import json
import math
import os
from pathlib import Path
import tempfile


def validate_points(points):
    if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 12:
        raise ValueError('Use 2–12 temperature / duty points')
    result = []
    for point in points:
        try:
            temp, duty = point
            temp, duty = float(temp), float(duty)
        except (TypeError, ValueError) as exc:
            raise ValueError('Each point needs a numeric temperature and duty') from exc
        if not math.isfinite(temp) or not math.isfinite(duty) or not 0 <= temp <= 100 or not 30 <= duty <= 100:
            raise ValueError('Temperatures: 0–100 °C; fan duty: 30–100%')
        if result and (temp <= result[-1][0] or duty < result[-1][1]):
            raise ValueError('Temperatures must increase and fan duty must not decrease')
        result.append((temp, duty))
    return tuple(result)


def curve_duty(points, temperature):
    points = validate_points(points)
    if temperature is None or not math.isfinite(temperature) or not -20 <= temperature <= 130:
        return 100
    if temperature >= 85:
        return 100
    if temperature <= points[0][0]:
        return points[0][1]
    for (t0, p0), (t1, p1) in zip(points, points[1:]):
        if temperature <= t1:
            return p0 + (p1 - p0) * (temperature - t0) / (t1 - t0)
    return points[-1][1]


def smooth_duty(previous, target, elapsed):
    # Raise immediately; lower no faster than two percentage points per second.
    return target if previous is None or target >= previous else max(target, previous - 2 * max(0, elapsed))


def sensor_id(sensor):
    if sensor.key.startswith('lhm:/'):
        return sensor.key
    path = Path(sensor.key).resolve()
    # hwmonN numbering can change after reboot; retain the physical device path.
    parent = path.parent
    if parent.name.startswith('hwmon') and parent.parent.name == 'hwmon':
        parent = parent.parent.parent
    return f'{parent}|{sensor.source}|{path.name}'


def profile_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'asiahorse-umbra/profiles.json'


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError('Invalid profile')
    name = str(profile.get('name', '')).strip()
    if not name or len(name) > 60:
        raise ValueError('Profile name must contain 1–60 characters')
    shortcut = str(profile.get('shortcut', ''))
    if shortcut not in ('', *map(str, range(1, 10))):
        raise ValueError('Shortcut must be empty or 1–9')
    sensor = profile.get('sensor', '')
    if not isinstance(sensor, str):
        raise ValueError('Invalid sensor identity')
    return dict(name=name, shortcut=shortcut, sensor=sensor,
                points=[list(p) for p in validate_points(profile.get('points', []))])


def load_profiles(path=None):
    path = path or profile_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('profiles'), list):
        raise ValueError('Unsupported profiles file')
    profiles = [validate_profile(p) for p in data['profiles']]
    validate_unique(profiles)
    return profiles


def validate_unique(profiles):
    names, keys = set(), set()
    for p in profiles:
        if p['name'] in names or p['shortcut'] and p['shortcut'] in keys:
            raise ValueError('Profile names and assigned shortcuts must be unique')
        names.add(p['name'])
        if p['shortcut']:
            keys.add(p['shortcut'])


def save_profiles(profiles, path=None):
    profiles = [validate_profile(p) for p in profiles]
    validate_unique(profiles)
    path = path or profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.profiles-', suffix='.json')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(dict(version=1, profiles=profiles), stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

