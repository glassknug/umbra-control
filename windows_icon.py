"""Set native small/large icons on Tk's outer Windows window after mapping."""
from pathlib import Path
import ctypes
from ctypes import wintypes


def set_native_icons(root, path):
    path=Path(path)
    if not path.is_file():raise OSError(f'Windows icon missing: {path}')
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
    user.GetAncestor.restype=wintypes.HWND
    user.LoadImageW.argtypes=[wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    user.LoadImageW.restype=wintypes.HANDLE
    user.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user.SendMessageW.restype=ctypes.c_ssize_t
    user.DestroyIcon.argtypes=[wintypes.HICON]
    user.DestroyIcon.restype=wintypes.BOOL
    user.GetSystemMetrics.argtypes=[ctypes.c_int]
    user.GetSystemMetrics.restype=ctypes.c_int
    hwnd=user.GetAncestor(root.winfo_id(),2)  # GA_ROOT: Tk's decorated outer HWND.
    if not hwnd:raise OSError('Windows top-level window not available')
    handles=[]
    root._umbra_native_icons=(user,handles)
    def release(event):
        if event.widget is root:
            for icon in handles:user.DestroyIcon(icon)
            handles.clear()
    root.bind('<Destroy>',release,add='+')
    for kind,metric in ((0,49),(1,11)):  # ICON_SMALL/SM_CXSMICON; ICON_BIG/SM_CXICON
        size=user.GetSystemMetrics(metric) or (16 if kind==0 else 32)
        icon=user.LoadImageW(None,str(path.resolve()),1,size,size,0x10)  # IMAGE_ICON; LR_LOADFROMFILE
        if not icon:raise OSError('Could not load Umbra Windows icon')
        handles.append(icon)
        user.SendMessageW(hwnd,0x80,kind,icon)  # WM_SETICON

