import io
import json
import queue
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from effects import Player
from fan_curves import sensor_id
from sensors import cpu_temperature
from windows_sensors import SensorCache, SensorService, decode_sample
from windows_sensor_helper import collect


def sample(value=45,identity='/amdcpu/0/temperature/2',label='Core (Tctl/Tdie)'):
    return json.dumps(dict(sensors=[dict(id=identity,source='/amdcpu/0',label=label,kind='temperature',value=value)]))


class WindowsSensorTests(unittest.TestCase):
    def test_valid_identity_and_cpu_selection(self):
        row=decode_sample(sample())[0]
        self.assertEqual(row.value,45)
        self.assertEqual(sensor_id(row),'lhm:/amdcpu/0/temperature/2')
        self.assertEqual(cpu_temperature([row]),row)
        gpu=decode_sample(sample(identity='/gpu-amd/0/temperature/0'))[0]
        self.assertIsNone(cpu_temperature([gpu]))

    def test_invalid_values_not_used(self):
        for value in (None,'45',True,0,float('nan'),float('inf'),-21,131):
            self.assertIsNone(decode_sample(sample(value))[0].value)
        for value in ('{}','[]','{"error":"reader failed"}', '{"sensors":null}'):
            with self.assertRaises(ValueError):decode_sample(value)
        data=json.loads(sample());data['sensors']*=2
        with self.assertRaises(ValueError):decode_sample(json.dumps(data))

    def test_cache_expires_on_silence_and_invalidates_on_error(self):
        now=[0.0];cache=SensorCache(clock=lambda:now[0])
        cache.accept(sample());self.assertEqual(cache.snapshot()[0].value,45)
        now[0]=5;self.assertIsNone(cache.snapshot()[0].value)
        self.assertIn('stale',cache.status())
        cache.accept(sample(50));self.assertEqual(cache.snapshot()[0].value,50)
        cache.fail('disconnected');self.assertIsNone(cache.snapshot()[0].value)
        self.assertIn('disconnected',cache.status())

    def test_first_sample_timeout_is_visible(self):
        now=[0.0];cache=SensorCache(clock=lambda:now[0])
        now[0]=6
        self.assertIn('No sensor samples',cache.status())
        cache.accept(sample())
        self.assertEqual(cache.snapshot()[0].value,45)

    def test_cpu_failure_reports_helper_access_in_ui_status(self):
        cache=SensorCache()
        data=json.loads(sample(0));data['diagnostics']={'elevated':'False','amd_module_loaded':'False','unrelated':'omit'}
        cache.accept(json.dumps(data))
        self.assertIn('elevated=False',cache.status())
        self.assertIn('loaded=False',cache.status())
        self.assertNotIn('unrelated',cache.diagnostics)
        self.assertIsNone(cache.snapshot()[0].value)

    def test_diagnostics_never_turn_missing_value_into_temperature(self):
        cache=SensorCache()
        data=json.loads(sample(None));data['diagnostics']={'raw_cpu_values':'/amdcpu/0/temperature/2=45','elevated':'True'}
        cache.accept(json.dumps(data))
        self.assertIsNone(cache.snapshot()[0].value)

    def test_reader_eof_or_bad_json_invalidates_previous_sample(self):
        for ending in (b'',b'not json\n'):
            service=SensorService(Path('.'))
            service.cache.accept(sample())
            service.process=types.SimpleNamespace(stdout=io.BytesIO(ending),stdin=io.BytesIO())
            service._read()
            self.assertIsNone(service.cache.snapshot()[0].value)

    def test_hardware_recursion_reads_and_updates(self):
        s=types.SimpleNamespace(SensorType='Temperature',Identifier='/amdcpu/0/temperature/2',Name='Core (Tctl/Tdie)',Value=48)
        child=types.SimpleNamespace(Update=Mock(),Sensors=[s],Identifier='/amdcpu/0',SubHardware=[])
        parent=types.SimpleNamespace(Update=Mock(),Sensors=[],Identifier='/root',SubHardware=[child])
        rows=collect(parent)
        parent.Update.assert_called_once();child.Update.assert_called_once()
        self.assertEqual(rows[0]['value'],48)

    def test_curve_requests_full_on_stale_sensor_and_quit(self):
        now=[0.0];cache=SensorCache(clock=lambda:now[0]);cache.accept(sample(30))
        h=Mock()
        with patch.object(sys,'platform','win32'),patch('effects.usb.open_hub',return_value=h),patch('effects.usb.write',return_value=65) as write,patch('effects.read_sensors',side_effect=cache.snapshot):
            p=Player()
            try:
                p.fan_curve([(35,50),(80,100)],'lhm:/amdcpu/0/temperature/2')
                self.assertEqual(p.fan_events.get(timeout=2)['duty'],50)
                now[0]=6
                event=p.fan_events.get(timeout=3)
                self.assertEqual(event['duty'],100);self.assertIn('unavailable',event['mode'])
            finally:p.close();p.thread.join(2)
            self.assertFalse(p.thread.is_alive())
            self.assertEqual(write.call_args.args[1][4:6],bytes([251,100]))

    def test_windows_startup_routes_to_windows_backend(self):
        import startup
        with patch.object(sys,'platform','win32'),patch('windows_startup.configure') as configure:
            startup.configure(None)
            configure.assert_called_once_with(None)

    def test_paused_reader_does_not_restart_itself(self):
        import windows_sensors as ws
        with patch.object(ws,'_service',None),patch.object(ws,'_paused',True),patch.object(ws,'library_directory') as folder:
            self.assertEqual(ws.read_sensors(),[])
            folder.assert_not_called()
            self.assertIn('stopped',ws.status())
