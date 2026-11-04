import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sensors import Sensor
from fan_curves import sensor_id
from rgb_layout import placement
from config_transfer import (MAX_BYTES, export_bundle, read_bundle, write_bundle,
                             validate_bundle, suggested_sensors, import_bundle)

class TransferTests(unittest.TestCase):
    def sample(self):
        sensor=Sensor('/sys/devices/example/hwmon/hwmon4/temp1_input','k10temp','Tctl','temperature',45)
        profile=dict(name='Balanced',shortcut='1',sensor=sensor_id(sensor),points=[[35,75],[80,100]])
        layout=dict(version=1,devices=[placement([],'Fan',.2,.3)])
        return export_bundle(layout,[profile],[sensor]),sensor

    def test_export_has_no_local_sensor_paths_or_startup(self):
        bundle,s=self.sample();text=json.dumps(bundle)
        self.assertNotIn('/sys/',text);self.assertNotIn('startup',text)
        self.assertEqual(bundle['fan_profiles'][0]['sensor_hint'],dict(source='k10temp',label='Tctl'))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json';write_bundle(path,bundle)
            self.assertEqual(read_bundle(path),bundle)

    def test_sensor_match_requires_unique_source_and_label(self):
        bundle,s=self.sample()
        self.assertEqual(suggested_sensors(bundle,[s])['Balanced'],sensor_id(s))
        other=Sensor('/sys/other/temp1_input','k10temp','Tctl','temperature',50)
        self.assertEqual(suggested_sensors(bundle,[s,other])['Balanced'],'')
        self.assertEqual(suggested_sensors(bundle,[])['Balanced'],'')

    def test_import_maps_to_this_computer_and_backs_up_original_bytes(self):
        bundle,s=self.sample()
        local=Sensor('/sys/local/temp2_input','k10temp','Tctl','temperature',40)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rgb=root/'rgb.json';fans=root/'fan.json'
            rgb.write_bytes(b'previous rgb');fans.write_bytes(b'previous fans')
            profiles,backup=import_bundle(bundle,{'Balanced':sensor_id(local)},[local],rgb,fans,root/'backups')
            self.assertEqual(profiles[0]['sensor'],sensor_id(local))
            self.assertEqual((backup/'rgb-layout.json').read_bytes(),b'previous rgb')
            self.assertEqual((backup/'profiles.json').read_bytes(),b'previous fans')
            self.assertEqual(json.loads(fans.read_text())['profiles'],profiles)

    def test_unmapped_profile_keeps_empty_sensor_and_stale_mapping_rejected(self):
        bundle,s=self.sample()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):import_bundle(bundle,{'Balanced':'/not-local'},[s],root/'rgb',root/'fan',root/'b')
            self.assertFalse((root/'rgb').exists())
            profiles,_=import_bundle(bundle,{},[],root/'rgb',root/'fan',root/'b')
            self.assertEqual(profiles[0]['sensor'],'')

    def test_second_file_failure_rolls_back_first(self):
        import config_transfer as transfer
        bundle,s=self.sample()
        for originally_present in (False,True):
            with self.subTest(present=originally_present), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);rgb=root/'rgb';fans=root/'fan'
                if originally_present:rgb.write_bytes(b'old-rgb')
                fans.write_bytes(b'old-fans')
                original=transfer.atomic_write
                def fail(path,data):
                    if path==fans:raise OSError('disk full')
                    return original(path,data)
                with patch('config_transfer.atomic_write',side_effect=fail):
                    with self.assertRaisesRegex(OSError,'previous files restored'):
                        import_bundle(bundle,{},[],rgb,fans,root/'b')
                self.assertEqual(rgb.exists(),originally_present)
                if originally_present:self.assertEqual(rgb.read_bytes(),b'old-rgb')
                self.assertEqual(fans.read_bytes(),b'old-fans')

    def test_invalid_format_points_duplicate_profiles_and_oversize_rejected(self):
        bundle,_=self.sample()
        for mutate in (lambda d:d.update(version=9),lambda d:d.update(startup='command'),
                       lambda d:d['fan_profiles'].append(dict(d['fan_profiles'][0])),
                       lambda d:d['fan_profiles'][0].update(points=[[35,10],[80,100]])):
            data=json.loads(json.dumps(bundle));mutate(data)
            with self.assertRaises(ValueError):validate_bundle(data)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json';path.write_bytes(b' '* (MAX_BYTES+1))
            with self.assertRaises(ValueError):read_bundle(path)
            path.write_text('{"x":NaN}')
            with self.assertRaises(ValueError):read_bundle(path)
