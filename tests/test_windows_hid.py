import sys
import types
import unittest
from unittest.mock import Mock, patch

import asiahorse as usb
from effects import Player


class WindowsHIDTests(unittest.TestCase):
    def fake(self, devices=None):
        handle = Mock()
        handle.write.return_value = 65
        module = types.SimpleNamespace(enumerate=Mock(return_value=devices if devices is not None else [{'path': b'umbra'}]), device=Mock(return_value=handle))
        return module, handle

    def test_reports_and_close(self):
        module, handle = self.fake()
        with patch.object(sys, 'platform', 'win32'), patch.dict(sys.modules, hid=module):
            h = usb.Hub()
            packet = usb.native(bytes([0]))
            self.assertEqual(usb.write(h, packet), 65)
            handle.write.assert_called_once_with(b'\0' + packet)
            for reply in (b'RB\x07\0', b'\0RB\x07\0'):
                handle.read.return_value = list(reply)
                self.assertEqual(usb.read_reply(h, 400), b'RB\x07\0')
                handle.read.assert_called_with(65, 400)
            h.close(); h.close()
            handle.close.assert_called_once()
            module.enumerate.assert_called_once_with(usb.VID, usb.PID)
            handle.open_path.assert_called_once_with(b'umbra')

    def test_refuses_missing_or_ambiguous_interfaces(self):
        for devices in ([], [{'path':b'a'}, {'path':b'b'}]):
            module, handle = self.fake(devices)
            with patch.object(sys, 'platform', 'win32'), patch.dict(sys.modules, hid=module), self.assertRaises(OSError):
                usb.Hub()
            handle.open_path.assert_not_called()

    def test_failed_open_closes_and_short_write_fails(self):
        module, handle = self.fake()
        handle.open_path.side_effect = OSError('busy')
        with patch.object(sys, 'platform', 'win32'), patch.dict(sys.modules, hid=module), self.assertRaises(OSError):
            usb.Hub()
        handle.close.assert_called_once()
        handle.write.return_value = 64
        with self.assertRaises(OSError):
            usb.write(types.SimpleNamespace(device=handle), bytes(64))

    def test_motor_entry_points_disabled(self):
        player = object.__new__(Player)
        with patch.object(sys, 'platform', 'win32'):
            for action in (lambda: player.fan_manual(75), lambda: player.fan_curve([(30,50),(80,100)], 'sensor'), lambda: player.fan_full()):
                with self.assertRaises(ValueError): action()
            with self.assertRaises(OSError): Player._fan_write(Mock(), 75)
