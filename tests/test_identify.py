import threading
import unittest
from unittest.mock import Mock,patch
from effects import Player,Settings,identify_frame

class IdentifyTests(unittest.TestCase):
    def test_only_chosen_port_changes_with_physical_offsets(self):
        original=[(12,34,56)]*6
        result=identify_frame([2,0,3,1],original,3,True)
        self.assertEqual(result[:2],original[:2]);self.assertEqual(result[2:5],[(0,160,120)]*3)
        self.assertEqual(result[5:],original[5:]);self.assertEqual(original,[(12,34,56)]*6)
        with self.assertRaises(ValueError):identify_frame([2,0,3,1],original,2,True)
        with self.assertRaises(ValueError):identify_frame([2],[],1,True)

    def test_identify_requires_known_rgb_and_rejects_invalid_port(self):
        p=Player()
        try:
            with self.assertRaises(ValueError):p.identify(0)
            p.identify(1)
            self.assertIn('apply an RGB mode first',p.events.get(timeout=2))
        finally:p.close();p.thread.join(2)

    def test_restores_latched_rgb_and_continues_manual_fan_control(self):
        hub=Mock();seen=threading.Event();frames=[]
        def capture(device,colors):
            frames.append(tuple(colors));seen.set()
        with patch.object(Player,'_connect',return_value=(hub,[2,2])),patch('effects.usb.write',return_value=65),patch('effects.send_frame',side_effect=capture):
            p=Player()
            try:
                p.start(Settings(color=(20,30,40),brightness=1))
                self.assertTrue(seen.wait(2))
                p.fan_manual(75);self.assertEqual(p.fan_events.get(timeout=2)['duty'],75)
                p.identify(2)
                messages=[]
                while True:
                    msg=p.events.get(timeout=5);messages.append(msg)
                    if 'identified · previous RGB restored' in msg:break
                self.assertEqual(frames[-1],((20,30,40),)*4)
                overlay=[f for f in frames if f[2:]==((0,160,120),)*2]
                self.assertTrue(overlay);self.assertEqual(overlay[0][:2],((20,30,40),)*2)
                self.assertEqual(p.fan_events.get(timeout=2)['duty'],75)
            finally:p.close();p.thread.join(2)

    def test_quit_during_identification_restores_colors(self):
        hub=Mock();base=threading.Event();blink=threading.Event();frames=[]
        def capture(device,colors):
            frames.append(tuple(colors))
            (blink if colors[0]==(0,160,120) else base).set()
        with patch.object(Player,'_connect',return_value=(hub,[2])),patch('effects.send_frame',side_effect=capture):
            p=Player()
            try:
                p.start(Settings(color=(10,20,30),brightness=1));self.assertTrue(base.wait(2))
                p.identify(1);self.assertTrue(blink.wait(2))
            finally:p.close();p.thread.join(2)
            self.assertEqual(frames[-1],((10,20,30),)*2)
