"""PC lighting layout: validated placement and one effect per Umbra RGB port."""
import json
import math
import os
from pathlib import Path
import tempfile

from effects import EFFECTS, SceneSettings, Settings

KINDS = ('Fan', 'LED strip', 'ARGB cable')


def layout_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'umbra-control/rgb-layout.json'


def validate_layout(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported RGB layout format')
    devices = data.get('devices')
    if not isinstance(devices, list) or len(devices) > 10:
        raise ValueError('Use up to 10 RGB port groups')
    ports, result = set(), []
    for d in devices:
        if not isinstance(d, dict):
            raise ValueError('Invalid RGB device')
        port = d.get('port')
        if type(port) is not int or not 1 <= port <= 10 or port in ports:
            raise ValueError('Assign each hub port (1–10) only once')
        name = d.get('name')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 32 or any(ord(c) < 32 for c in name):
            raise ValueError('Names need 1–32 printable characters')
        if d.get('kind') not in KINDS or d.get('orientation') not in ('Horizontal','Vertical'):
            raise ValueError('Invalid device type or orientation')
        fan_count=d.get('fan_count',1)
        if type(fan_count) is not int or not 1 <= fan_count <= 10:
            raise ValueError('Fan count must be a whole number from 1 to 10')
        xy=[]
        for axis in ('x','y'):
            v=d.get(axis)
            if type(v) not in (float,int) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError('Positions must be inside the PC case')
            xy.append(float(v))
        color=d.get('color')
        if not isinstance(color,str) or len(color)!=7 or not color.startswith('#'):
            raise ValueError('Use a color such as #71e6cf')
        try: int(color[1:],16)
        except ValueError as exc: raise ValueError('Invalid RGB color') from exc
        if d.get('effect') not in EFFECTS:
            raise ValueError('Unknown lighting effect')
        values=[]
        for key,low,high in (('brightness',0,100),('speed',.25,3)):
            v=d.get(key)
            if type(v) not in (int,float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError(f'{key.capitalize()} must be {low}–{high}')
            values.append(float(v))
        ports.add(port)
        result.append(dict(port=port,name=name.strip(),kind=d['kind'],orientation=d['orientation'],x=xy[0],y=xy[1],
                           color=color.lower(),effect=d['effect'],brightness=values[0],speed=values[1],fan_count=fan_count))
    return dict(version=1,devices=result)


def placement(devices,kind,x,y):
    used={d['port'] for d in devices}
    port=next((p for p in range(1,11) if p not in used),None)
    if port is None:
        raise ValueError('All 10 hub ports are already placed')
    d=dict(port=port,name=f'{kind} {port}',kind=kind,orientation='Horizontal',x=x,y=y,
           color='#71e6cf',effect='Solid color',brightness=70,speed=1,fan_count=1)
    return validate_layout(dict(version=1,devices=[d]))['devices'][0]


def scene_settings(data):
    devices=validate_layout(data)['devices']
    if not devices:
        raise ValueError('Add at least one RGB device first')
    return SceneSettings(tuple((d['port'],Settings(d['effect'],tuple(int(d['color'][i:i+2],16) for i in (1,3,5)),
                                                d['brightness']/100,d['speed'])) for d in devices))


def load_layout(path=None):
    path=path or layout_path()
    if not path.exists():
        return dict(version=1,devices=[])
    return validate_layout(json.loads(path.read_text(encoding='utf-8')))


def save_layout(data,path=None):
    data=validate_layout(data)
    path=path or layout_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.rgb-layout-',suffix='.json')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def fan_geometry(count, orientation, available_width, available_height):
    """Return grouped fan centers and size; fit the chain inside the case."""
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError('Fan count must be 1–10')
    vertical = orientation == 'Vertical'
    natural_length = 54 + 62 * (count - 1)
    natural_width, natural_height = (54, natural_length) if vertical else (natural_length, 54)
    scale = min(1, available_width / natural_width, available_height / natural_height)
    radius = 27 * scale
    offsets = []
    for i in range(count):
        offset = (i - (count - 1) / 2) * 62 * scale
        offsets.append((0, offset) if vertical else (offset, 0))
    return offsets, radius, natural_width * scale, natural_height * scale
