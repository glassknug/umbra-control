import sys
import queue
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

    def test_motor_requests_and_curves_limited(self):
        player = object.__new__(Player)
        player.commands = queue.Queue()
        with patch.object(sys, 'platform', 'win32'):
            player.fan_manual(75); player.fan_full()
            self.assertEqual(player.commands.get_nowait(),('fan_manual',75.0))
            self.assertEqual(player.commands.get_nowait(),('fan_manual',100.0))
            player.fan_manual(50)
            self.assertEqual(player.commands.get_nowait(),('fan_manual',50.0))
            player.fan_manual(80)
            self.assertEqual(player.commands.get_nowait(),('fan_manual',80.0))
            for value in (30,49,101,float('nan')):
                with self.assertRaises(ValueError): player.fan_manual(value)
            with self.assertRaises(ValueError): player.fan_curve([(30,50),(80,100)],'sensor')
            with self.assertRaises(ValueError): player.fan_curve([(30,49),(80,100)],'lhm:/amdcpu/0/temperature/0')
            player.fan_curve([(30,50),(80,100)],'lhm:/amdcpu/0/temperature/0')
            self.assertEqual(player.commands.get_nowait()[0],'fan_curve')
            with self.assertRaises(OSError): Player._fan_write(Mock(),49)

    def test_motor_claim_packets_and_failed_write(self):
        with patch.object(sys,'platform','win32'),patch.object(usb,'write',return_value=65) as write:
            h=object()
            Player._fan_write(h,50,True)
            self.assertEqual([call.args[1] for call in write.call_args_list],
                             [usb.native(bytes(b)) for b in ([251,100],[8,1],[251,50])])
            write.return_value=64
            with self.assertRaises(OSError): Player._fan_write(h,100)

    def test_worker_restores_full_duty_on_quit(self):
        h=Mock()
        with patch.object(sys,'platform','win32'),patch.object(usb,'open_hub',return_value=h),patch.object(usb,'write',return_value=65) as write:
            player=Player()
            try:
                player.fan_manual(75)
                self.assertEqual(player.fan_events.get(timeout=2)['duty'],75)
            finally:
                player.close();player.thread.join(2)
            self.assertFalse(player.thread.is_alive())
            self.assertEqual(write.call_args.args[1],usb.native(bytes([251,100])))
            h.close.assert_called_once()
