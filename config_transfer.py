"""Portable, data-only configuration bundles with validated import and rollback."""
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from fan_curves import profile_path, sensor_id, validate_profile, validate_unique
from rgb_layout import layout_path, validate_layout

FORMAT = 'umbra-control-configuration'
MAX_BYTES = 256 * 1024


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'Invalid {label} fields')


def validate_bundle(data):
    keys(data, ('format','version','rgb_layout','fan_profiles'), 'configuration')
    if data['format'] != FORMAT or type(data['version']) is not int or data['version'] != 1:
        raise ValueError('Unsupported configuration format/version')
    keys(data['rgb_layout'], ('version','devices'), 'RGB layout')
    layout = validate_layout(data['rgb_layout'])
    if not isinstance(data['fan_profiles'], list) or len(data['fan_profiles']) > 50:
        raise ValueError('Use up to 50 fan profiles')
    profiles=[]
    for p in data['fan_profiles']:
        keys(p, ('name','shortcut','points','sensor_hint'), 'fan profile')
        if not isinstance(p['name'], str) or not isinstance(p['shortcut'], str):
            raise ValueError('Invalid profile name/shortcut')
        hint=p['sensor_hint']
        if hint is not None:
            keys(hint, ('source','label'), 'sensor hint')
            if any(not isinstance(v,str) or not 1 <= len(v) <= 100 or any(ord(c)<32 for c in v) for v in hint.values()):
                raise ValueError('Invalid sensor hint')
        clean=validate_profile(dict(name=p['name'],shortcut=p['shortcut'],points=p['points'],sensor=''))
        clean.pop('sensor')
        clean['sensor_hint']=hint
        profiles.append(clean)
    validate_unique(profiles)
    return dict(format=FORMAT,version=1,rgb_layout=layout,fan_profiles=profiles)


def export_bundle(layout, profiles, sensors):
    result=[]
    for p in profiles:
        p=validate_profile(p)
        matching=[s for s in sensors if s.kind=='temperature' and sensor_id(s)==p['sensor']]
        hint=dict(source=matching[0].source,label=matching[0].label) if len(matching)==1 else None
        result.append(dict(name=p['name'],shortcut=p['shortcut'],points=p['points'],sensor_hint=hint))
    return validate_bundle(dict(format=FORMAT,version=1,rgb_layout=layout,fan_profiles=result))


def read_bundle(path):
    with Path(path).open('rb') as f:
        raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('Configuration is too large (maximum 256 KiB)')
    def invalid(value):
        raise ValueError(f'Invalid numeric value: {value}')
    try:
        return validate_bundle(json.loads(raw.decode('utf-8'),parse_constant=invalid))
    except (UnicodeDecodeError,RecursionError) as exc:
        raise ValueError('Invalid configuration JSON') from exc


def atomic_write(path, data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.transfer-')
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def write_bundle(path, data):
    data=validate_bundle(data)
    raw=(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    if len(raw)>MAX_BYTES:
        raise ValueError('Configuration is too large')
    atomic_write(path,raw)


def suggested_sensors(bundle, sensors):
    result={}
    for p in bundle['fan_profiles']:
        h=p['sensor_hint']
        matches=[s for s in sensors if h and s.kind=='temperature' and s.source==h['source'] and s.label==h['label']]
        result[p['name']]=sensor_id(matches[0]) if len(matches)==1 else ''
    return result


def import_bundle(bundle, mappings, sensors, rgb_path=None, fan_path=None, backup_root=None):
    bundle=validate_bundle(bundle)
    valid_sensors={sensor_id(s) for s in sensors if s.kind=='temperature'}
    profiles=[]
    for p in bundle['fan_profiles']:
        identity=mappings.get(p['name'],'')
        if identity and identity not in valid_sensors:
            raise ValueError('A selected temperature sensor is no longer available; reload the preview')
        profiles.append(validate_profile(dict(name=p['name'],shortcut=p['shortcut'],points=p['points'],sensor=identity)))
    rgb_path=Path(rgb_path) if rgb_path is not None else layout_path()
    fan_path=Path(fan_path) if fan_path is not None else profile_path()
    if rgb_path.resolve()==fan_path.resolve():
        raise ValueError('Configuration destinations must be different')
    targets=[rgb_path,fan_path]
    previous=[p.read_bytes() if p.exists() else None for p in targets]
    root=Path(backup_root) if backup_root is not None else layout_path().parent/'backups'
    root.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-')
    backup=Path(tempfile.mkdtemp(prefix=stamp,dir=root))
    # Preserve original bytes before either destination changes.
    for name,raw in zip(('rgb-layout.json','profiles.json'),previous):
        if raw is not None:(backup/name).write_bytes(raw)
    (backup/'manifest.json').write_text(json.dumps(dict(rgb_existed=previous[0] is not None,profiles_existed=previous[1] is not None)))
    payloads=[bundle['rgb_layout'],dict(version=1,profiles=profiles)]
    changed=[]
    try:
        for i,(path,data) in enumerate(zip(targets,payloads)):
            atomic_write(path,(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
            changed.append(i)
    except OSError as exc:
        errors=[]
        for i in reversed(changed):
            try:
                if previous[i] is None:targets[i].unlink(missing_ok=True)
                else:atomic_write(targets[i],previous[i])
            except OSError as rollback:errors.append(str(rollback))
        if errors:
            raise OSError(f'Import failed; rollback incomplete. Original files are in {backup}: {errors}') from exc
        raise OSError(f'Import failed; previous files restored. Backup: {backup}. {exc}') from exc
    return profiles,backup
