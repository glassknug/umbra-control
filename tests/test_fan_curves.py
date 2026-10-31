import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from fan_curves import curve_duty, load_profiles, save_profiles, smooth_duty, validate_points
from effects import Player, Settings


class CurveTests(unittest.TestCase):
    def test_interpolation_and_failsafe(self):
        points = [(35,75),(60,85),(80,100)]
        self.assertEqual(curve_duty(points, 0), 75)
        self.assertEqual(curve_duty(points, 47.5), 80)
        for temp in (None, float('nan'), -100, 1000, 85):
            self.assertEqual(curve_duty(points, temp), 100)
        self.assertEqual(curve_duty([(20,30),(80,30)], 85), 100)
        self.assertEqual(smooth_duty(100, 75, 1), 98)
        self.assertEqual(smooth_duty(75, 100, .01), 100)

    def test_invalid_curves(self):
        for points in ([], [(30,20),(80,100)], [(40,80),(40,100)], [(40,100),(80,75)], [(float('nan'),75),(80,100)]):
            with self.assertRaises(ValueError):
                validate_points(points)

    def test_profile_roundtrip_and_duplicate_shortcut(self):
        profile = dict(name='Balanced', shortcut='1', sensor='cpu', points=[[35,75],[80,100]])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config/profiles.json'
            self.assertEqual(load_profiles(path), [])
            save_profiles([profile], path)
            self.assertEqual(load_profiles(path), [profile])
            with self.assertRaises(ValueError):
                save_profiles([profile, dict(profile, name='Other')], path)
            self.assertEqual(load_profiles(path), [profile])


class FanWorkerTests(unittest.TestCase):
    def sample(self, player):
        result = player.fan_events.get(timeout=3)
        self.assertNotIn('USB error', result['mode'])
        return result

    @patch('effects.usb.write', return_value=65)
    @patch('effects.usb.open_hub')
    def test_manual_claim_and_full_duty_on_close(self, opened, write):
        hub = opened.return_value
        player = Player()
        try:
            player.fan_manual(75)
            self.assertEqual(self.sample(player)['duty'], 75)
        finally:
            player.close()
            player.thread.join(3)
        packets = [call.args[1] for call in write.call_args_list]
        self.assertEqual([p[4:6] for p in packets[:3]], [b'\xfb\x64',b'\x08\x01',b'\xfb\x4b'])
        self.assertEqual(packets[-1][4:6], b'\xfb\x64')
        hub.close.assert_called_once()

    @patch('effects.read_sensors', return_value=[])
    @patch('effects.usb.write', return_value=65)
    @patch('effects.usb.open_hub')
    def test_missing_sensor_requests_full_duty(self, opened, write, sensors):
        player = Player()
        try:
            player.fan_curve([(35,75),(80,100)], 'missing-cpu')
            sample = self.sample(player)
            self.assertEqual(sample['duty'], 100)
            self.assertIn('Sensor unavailable', sample['mode'])
        finally:
            player.close()
            player.thread.join(3)

    @patch('effects.send_frame')
    @patch('effects.usb.write', return_value=65)
    @patch('effects.usb.open_hub')
    @patch.object(Player, '_connect')
    def test_rgb_and_fan_commands_are_not_dropped(self, connected, opened, write, frame):
        connected.return_value = (Mock(), [12])
        player = Player()
        try:
            player.start(Settings(effect='Rainbow'))
            player.fan_manual(75)
            self.assertEqual(self.sample(player)['duty'], 75)
            self.assertTrue(frame.called)
            player.stop()
            player.fan_full()
            self.assertEqual(self.sample(player)['duty'], 100)
        finally:
            player.close()
            player.thread.join(3)
        self.assertFalse(player.thread.is_alive())

    @patch('effects.usb.write', side_effect=OSError('disconnected'))
    @patch('effects.usb.open_hub')
    def test_usb_failure_is_reported(self, opened, write):
        player = Player()
        try:
            player.fan_manual(75)
            sample = player.fan_events.get(timeout=3)
            self.assertIsNone(sample['duty'])
            self.assertIn('USB error', sample['mode'])
            self.assertGreaterEqual(write.call_count, 2)
        finally:
            player.close()
            player.thread.join(3)
