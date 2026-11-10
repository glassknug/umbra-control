"""Build two Windows executables, smoke-test them and create a distributable ZIP."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent
NAME='UmbraControl-Windows-preview'


def build():
    if sys.platform!='win32':raise RuntimeError('Build this package on Windows; PyInstaller is not a Windows cross-compiler')
    # Private temporary output avoids deleting or mixing user files from an older build.
    with tempfile.TemporaryDirectory(prefix='umbra-build-') as temporary:
        stage=Path(temporary)
        common=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--noupx',
                '--distpath',str(stage/'dist'),'--workpath',str(stage/'work'),'--specpath',str(stage),
                '--icon',str(ROOT/'umbra-icon.ico')]
        subprocess.run(common+['--onedir','--windowed','--name','UmbraControl',
            '--version-file',str(ROOT/'windows_version.txt'),
            '--add-data',f'{ROOT / "umbra-icon.ico"}:.','--add-data',f'{ROOT / "umbra-icon.png"}:.',
            str(ROOT/'windows_app.py')],cwd=ROOT,check=True)
        helper_version=stage/'helper_version.txt'
        helper_version.write_text((ROOT/'windows_version.txt').read_text(encoding='utf-8').replace("'UmbraControl'","'UmbraSensorHelper'").replace('UmbraControl.exe','UmbraSensorHelper.exe').replace('Umbra Control for Windows preview','Umbra sensor helper'),encoding='utf-8')
        subprocess.run(common+['--onedir','--console','--name','UmbraSensorHelper',
            '--version-file',str(helper_version),
            '--collect-all','pythonnet','--collect-all','clr_loader','--hidden-import','clr',
            '--hidden-import','_cffi_backend',str(ROOT/'windows_sensor_helper.py')],cwd=ROOT,check=True)
        app=stage/'dist/UmbraControl'
        shutil.copytree(stage/'dist/UmbraSensorHelper',app/'sensor-helper')
        for name in ('LICENSE','WINDOWS_PACKAGE.txt','WINDOWS_SIGNING.md'):
            shutil.copy2(ROOT/name,app/name)
        (app/'Create desktop shortcut.cmd').write_text('@echo off\nstart "" "%~dp0UmbraControl.exe" --create-shortcut\n',encoding='ascii')
        report=stage/'gui-self-test.json'
        run=subprocess.run([str(app/'UmbraControl.exe'),'--self-test',str(report)],timeout=90)
        if run.returncode or not report.is_file() or not json.loads(report.read_text(encoding='utf-8'))['passed']:
            raise RuntimeError('GUI package self-test failed: '+(report.read_text(encoding='utf-8') if report.exists() else str(run.returncode)))
        helper=subprocess.run([str(app/'sensor-helper/UmbraSensorHelper.exe'),'--self-test'],
                              capture_output=True,text=True,timeout=90)
        if helper.returncode or json.loads(helper.stdout).get('self_test')!='passed':
            raise RuntimeError('Sensor helper package self-test failed: '+helper.stdout+helper.stderr)
        (app/'BUILD_CHECKS.json').write_text(json.dumps(dict(gui=json.loads(report.read_text(encoding='utf-8')),
            sensor_helper=json.loads(helper.stdout),hardware_tested=False,signed=False),indent=2),encoding='utf-8')
        # Include package licensing produced by PyInstaller for bundled Python dependencies.
        licenses=app/'THIRD_PARTY';licenses.mkdir()
        from importlib.metadata import distribution
        for package in ('hidapi','pythonnet','clr_loader','cffi','pycparser','pyinstaller'):
            dist=distribution(package)
            for file in dist.files or []:
                if 'license' in file.name.lower() or 'copying' in file.name.lower():
                    source=Path(dist.locate_file(file))
                    if source.is_file():
                        destination=licenses/package/str(file)
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(source,destination)
        (licenses/'PYTHON-LICENSE.txt').write_text(Path(sys.base_prefix,'LICENSE.txt').read_text(encoding='utf-8'),encoding='utf-8')
        for name in ('tcl8.6','tk8.6'):
            source=Path(sys.base_prefix)/'tcl'/name/'license.terms'
            if source.is_file():shutil.copy2(source,licenses/(name+'-license.terms'))
        output=ROOT/'dist';output.mkdir(exist_ok=True)
        archive=output/(NAME+'.zip')
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for file in sorted(app.rglob('*')):
                if file.is_file():z.write(file,Path(NAME)/file.relative_to(app))
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        (output/(NAME+'.sha256')).write_text(digest+'  '+archive.name+'\n',encoding='ascii')
        print('Created:',archive)
        print('SHA256:',digest)
        return archive


if __name__=='__main__':build()
