"""Pinned, unmodified sensor dependency used by the Windows package builder."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile
import io

VERSION = '0.9.6'
URL = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip'
SHA256 = '086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001'
SOURCE = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/tree/v0.9.6'


def install_sensor_bundle(destination):
    destination = Path(destination)
    data = urllib.request.urlopen(URL, timeout=90).read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError('LibreHardwareMonitor download checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Unsafe sensor archive path')
        archive.extractall(destination)
    for name in ('LibreHardwareMonitorLib.dll', 'LibreHardwareMonitor.exe'):
        if not (destination / name).is_file():
            raise RuntimeError('Incomplete LibreHardwareMonitor bundle: ' + name)
    for name in ('LICENSE', 'THIRD-PARTY-NOTICES.txt'):
        url = 'https://raw.githubusercontent.com/LibreHardwareMonitor/LibreHardwareMonitor/v0.9.6/' + name
        (destination / name).write_bytes(urllib.request.urlopen(url, timeout=45).read())
    (destination / 'SOURCE.txt').write_text(
        'Unmodified LibreHardwareMonitor ' + VERSION + '\nSource and license: ' + SOURCE +
        '\nDownload: ' + URL + '\nSHA256: ' + SHA256 + '\n', encoding='utf-8')
