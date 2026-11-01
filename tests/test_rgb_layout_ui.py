from unittest.mock import Mock, patch
import unittest
from rgb_layout import KINDS
from rgb_layout_ui import RGBLayoutTab
from effects import SceneSettings

class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value

class RGBLayoutUITests(unittest.TestCase):
    def tab(self):
        tab=RGBLayoutTab.__new__(RGBLayoutTab)
        tab.player=Mock();tab.devices=[];tab.selected=None;tab.status=Value('');tab.dirty=False
        tab.refresh_choices=Mock();tab.select=Mock();tab.root=Mock()
        return tab

    def test_layout_edit_sends_no_commands(self):
        tab=self.tab();tab.add(KINDS[2],.2,.3)
        tab.selected=0;tab.devices[0].update(x=.8,y=.7);tab.mark_dirty();tab.remove()
        self.assertEqual(tab.devices,[]);self.assertEqual(tab.player.mock_calls,[])

    def test_apply_uses_only_rgb_worker(self):
        tab=self.tab();tab.add(KINDS[0]);tab.selected=None;tab.apply()
        tab.player.start.assert_called_once()
        self.assertIsInstance(tab.player.start.call_args.args[0],SceneSettings)
        self.assertEqual(len(tab.player.mock_calls),1)

    @patch('rgb_layout_ui.messagebox.showerror')
    def test_invalid_port_blocks_apply(self,error):
        tab=self.tab();tab.add(KINDS[0]);tab.devices[0]['port']=0;tab.selected=None;tab.apply()
        self.assertEqual(tab.player.mock_calls,[]);error.assert_called_once()

    @patch('rgb_layout_ui.save_layout')
    def test_save_does_not_change_hardware(self,save):
        tab=self.tab();tab.add(KINDS[1]);tab.selected=None;tab.save()
        save.assert_called_once();self.assertEqual(tab.player.mock_calls,[])
