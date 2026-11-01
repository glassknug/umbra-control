import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from effects import SceneSettings, Settings, make_frame, static_settings
from rgb_layout import KINDS, load_layout, placement, save_layout, scene_settings, validate_layout

class RGBLayoutTests(unittest.TestCase):
    def test_shapes_roundtrip_and_settings_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config/rgb-layout.json'
            self.assertEqual(load_layout(path)['devices'],[])
            ds=[]
            for kind in KINDS:ds.append(placement(ds,kind,.2,.7))
            ds[2].update(name='GPU cable',orientation='Vertical',effect='Chase',color='#ff0099',speed=2)
            data=dict(version=1,devices=ds);save_layout(data,path)
            self.assertEqual(load_layout(path),data)
            settings=scene_settings(data);ds[2]['color']='#000000'
            self.assertEqual(dict(settings.ports)[3].color,(255,0,153))
            self.assertFalse(static_settings(settings))

    def test_invalid_layout_and_duplicate_ports(self):
        d=placement([],KINDS[0],.5,.5)
        with self.assertRaises(ValueError):validate_layout(dict(version=1,devices=[d,dict(d)]))
        for key,value in [('port',True),('port',11),('x',float('nan')),('y',1.2),('name','\n'),('kind','USB controller'),('orientation','Diagonal'),('color','#zzzzzz'),('color','blue'),('brightness',101),('speed',0),('effect','unknown')]:
            bad=dict(d);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_layout(dict(version=1,devices=[bad]))

    def test_capacity_and_reusing_port(self):
        ds=[]
        for _ in range(10):ds.append(placement(ds,KINDS[0],.5,.5))
        with self.assertRaises(ValueError):placement(ds,KINDS[1],.5,.5)
        del ds[3];self.assertEqual(placement(ds,KINDS[2],.5,.5)['port'],4)

    def test_failed_save_preserves_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rgb-layout.json'
            original=dict(version=1,devices=[placement([],KINDS[0],.2,.3)]);save_layout(original,path)
            updated=copy.deepcopy(original);updated['devices'][0]['x']=.9
            with patch('rgb_layout.os.replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):save_layout(updated,path)
            self.assertEqual(load_layout(path),original);self.assertEqual(list(Path(folder).iterdir()),[path])

    def test_corrupt_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rgb-layout.json'
            for text in ('broken','{"version":2,"devices":[]}'):
                path.write_text(text)
                with self.assertRaises(ValueError):load_layout(path)
                self.assertEqual(path.read_text(),text)

    def test_physical_port_offsets_with_empty_and_unassigned_ports(self):
        scene=SceneSettings(((1,Settings(color=(255,0,0),brightness=1)),(3,Settings(color=(0,0,255),brightness=.5))))
        self.assertEqual(make_frame([2,0,3,1],scene,0),[(255,0,0)]*2+[(0,0,128)]*3+[(0,0,0)])
        self.assertTrue(static_settings(scene))
        self.assertEqual(make_frame([1,2,1],scene,0),[(255,0,0),(0,0,0),(0,0,0),(0,0,128)])

    def test_independent_effects(self):
        scene=SceneSettings(((1,Settings('Solid color',(255,0,0),1,1)),(2,Settings('Breathing',(0,255,0),1,2))))
        frame=make_frame([2,2],scene,1)
        self.assertEqual(frame[:2],[(255,0,0)]*2);self.assertEqual(frame[2:],[(0,0,0)]*2)
        self.assertFalse(static_settings(scene))
        with self.assertRaises(ValueError):scene_settings(dict(version=1,devices=[]))
        with self.assertRaises(ValueError):SceneSettings(((1,Settings()),(1,Settings())))

class RGBSceneWorkerTests(unittest.TestCase):
    def test_scene_and_motor_control_share_worker_without_changing_port_colors(self):
        import threading
        from unittest.mock import Mock
        from effects import Player
        hub=Mock();sent=threading.Event();frames=[]
        def capture(device,colors):
            frames.append(colors);sent.set()
        with patch('effects.usb.open_hub',return_value=hub), patch.object(Player,'_connect',return_value=(hub,[1,0,2])), patch('effects.usb.write',return_value=65) as write, patch('effects.send_frame',side_effect=capture):
            p=Player()
            try:
                p.fan_manual(75)
                sample=p.fan_events.get(timeout=2)
                self.assertEqual(sample['duty'],75)
                p.start(SceneSettings(((1,Settings(color=(255,0,0),brightness=1)),(3,Settings(color=(0,0,255),brightness=1)))))
                self.assertTrue(sent.wait(2))
                self.assertEqual(frames[-1],[(255,0,0),(0,0,255),(0,0,255)])
                self.assertEqual(p.port_counts,(1,0,2))
                self.assertEqual(p.fan_events.get(timeout=2)['duty'],75)
                # All motor writes still use the existing shared command bodies.
                from asiahorse import native
                allowed={native(bytes([0xFB,100])),native(bytes([0x08,1])),native(bytes([0xFB,75]))}
                self.assertTrue(all(call.args[1] in allowed for call in write.call_args_list))
            finally:
                p.close();p.thread.join(2)
            self.assertFalse(p.thread.is_alive())

class DaisyChainTests(unittest.TestCase):
    def test_legacy_layout_defaults_to_one_and_count_roundtrips(self):
        d=placement([],KINDS[0],.5,.5)
        d.pop('fan_count')
        normalized=validate_layout(dict(version=1,devices=[d]))
        self.assertEqual(normalized['devices'][0]['fan_count'],1)
        normalized['devices'][0]['fan_count']=3
        normalized['devices'][0]['orientation']='Vertical'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'layout.json'
            save_layout(normalized,path)
            self.assertEqual(load_layout(path)['devices'][0]['fan_count'],3)
        for value in (0,-1,11,2.5,True,'3',None):
            d['fan_count']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_layout(dict(version=1,devices=[d]))

    def test_fan_count_does_not_change_rgb_stream_or_port_assignment(self):
        d=placement([],KINDS[0],.5,.5)
        one=scene_settings(dict(version=1,devices=[d]))
        d['fan_count']=3
        three=scene_settings(dict(version=1,devices=[d]))
        self.assertEqual(one,three)
        self.assertEqual(make_frame([24,16],one,.5),make_frame([24,16],three,.5))

    def test_geometry_rotates_and_fits_whole_group_inside_available_space(self):
        from rgb_layout import fan_geometry
        for count in (1,2,3,10):
            for orientation in ('Horizontal','Vertical'):
                centers,r,w,h=fan_geometry(count,orientation,210,160)
                self.assertEqual(len(centers),count)
                self.assertLessEqual(w,210);self.assertLessEqual(h,160)
                for x,y in centers:
                    self.assertLessEqual(abs(x)+r,w/2+.00001)
                    self.assertLessEqual(abs(y)+r,h/2+.00001)
                self.assertEqual(sum(x for x,_ in centers),0)
                self.assertAlmostEqual(sum(y for _,y in centers),0)
        centers,_,_,_=fan_geometry(3,'Vertical',300,300)
        self.assertTrue(all(x==0 for x,_ in centers))
        self.assertEqual(len({y for _,y in centers}),3)
