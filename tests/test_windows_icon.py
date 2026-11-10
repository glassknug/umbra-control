from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from windows_icon import set_native_icons


class WindowsIconTests(unittest.TestCase):
    def test_outer_window_gets_both_icons_with_live_handles(self):
        user=Mock();user.GetAncestor.return_value=12345
        user.GetSystemMetrics.side_effect=[16,32]
        user.LoadImageW.side_effect=[9001,9002]
        root=Mock();root.winfo_id.return_value=56789
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'icon.ico';path.touch()
            with patch('windows_icon.ctypes.WinDLL',return_value=user,create=True):set_native_icons(root,path)
        user.GetAncestor.assert_called_once_with(56789,2)
        self.assertEqual([c.args for c in user.SendMessageW.call_args_list],[(12345,0x80,0,9001),(12345,0x80,1,9002)])
        user.DestroyIcon.assert_not_called()
        cleanup=root.bind.call_args.args[1]
        event=Mock();event.widget=root;cleanup(event)
        self.assertEqual([c.args[0] for c in user.DestroyIcon.call_args_list],[9001,9002])

    def test_missing_icon_does_not_call_windows_api(self):
        with tempfile.TemporaryDirectory() as folder,patch('windows_icon.ctypes.WinDLL',create=True) as native:
            with self.assertRaises(OSError):set_native_icons(Mock(),Path(folder)/'missing.ico')
            native.assert_not_called()
