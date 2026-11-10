"""Opt-in desktop-session startup with a validated curve snapshot."""
import json
import os
from pathlib import Path
import sys
from fan_curves import validate_profile
from install_desktop import desktop_quote


def paths():
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'umbra-control/startup.json', base / 'autostart/umbra-control.desktop'


def load():
    if sys.platform == 'win32':
        from windows_startup import load as windows_load
        return windows_load()
    config, entry = paths()
    if not entry.exists() or not config.exists():
        return None
    return validate_profile(json.loads(config.read_text(encoding='utf-8')))


def configure(profile):
    if sys.platform == 'win32':
        from windows_startup import configure as windows_configure
        return windows_configure(profile)
    config, entry = paths()
    if profile is None:
        entry.unlink(missing_ok=True)
        config.unlink(missing_ok=True)
        return
    profile = validate_profile(profile)
    config.parent.mkdir(parents=True, exist_ok=True)
    entry.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(profile), encoding='utf-8')
    script = Path(__file__).resolve().with_name('asiahorse_gui.py')
    command = f'{desktop_quote(sys.executable)} {desktop_quote(str(script))} --autostart'
    entry.write_text('[Desktop Entry]\nType=Application\nName=Umbra Control\n'
                     f'Exec={command}\nTerminal=false\nIcon=asiahorse-umbra\n', encoding='utf-8')

