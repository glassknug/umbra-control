"""Guided sensor setup; never installs drivers or changes file trust silently."""
import os
from pathlib import Path
import sys
import webbrowser


def bundled_library():
    if not getattr(sys, 'frozen', False):
        return None
    folder = Path(sys.executable).parent / 'LibreHardwareMonitor'
    return folder if (folder / 'LibreHardwareMonitorLib.dll').is_file() else None


def is_elevated():
    if sys.platform != 'win32':
        return False
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def show(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import windows_sensors
    dialog = tk.Toplevel(parent)
    dialog.title('Sensor setup')
    dialog.transient(parent)
    dialog.resizable(False, False)
    body = ttk.Frame(dialog, padding=20); body.pack(fill='both', expand=True)
    ttk.Label(body, text='Windows sensor setup', style='Title.TLabel').pack(anchor='w')
    status = tk.StringVar()
    def refresh():
        library = windows_sensors.library_directory()
        status.set('Sensor library: ' + (str(library) if library else 'not configured') +
                   '\nAdministrator access: ' + ('enabled' if is_elevated() else 'not enabled') +
                   '\n\n' + windows_sensors.status())
    ttk.Label(body, textvariable=status, wraplength=600).pack(anchor='w', pady=12)
    ttk.Label(body, text='1. The installer includes LibreHardwareMonitor; no folder selection is normally needed.\n'
              '2. Open its official sensor tool below. If it asks to install PawnIO, review and accept its driver installer.\n'
              '3. Save your changes, close this guide and use Restart as administrator in the main window for CPU temperatures and login-startup setup.\n'
              '4. Reopen this guide and restart the sensor reader. RGB works without sensor setup.',
              wraplength=600).pack(anchor='w', pady=8)
    def open_monitor():
        folder = windows_sensors.library_directory()
        exe = folder / 'LibreHardwareMonitor.exe' if folder else None
        if not exe or not exe.is_file():
            webbrowser.open('https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6')
            return
        os.startfile(str(exe))
    def choose():
        folder = filedialog.askdirectory(parent=dialog, title='LibreHardwareMonitor folder')
        if folder:
            try: windows_sensors.restart(folder)
            except (OSError, ValueError) as exc: messagebox.showerror('Sensor setup', str(exc), parent=dialog)
        refresh()
    def restart():
        windows_sensors.restart(); refresh()
    ttk.Button(body, text='Open LibreHardwareMonitor / PawnIO setup', command=open_monitor).pack(fill='x', pady=4)
    ttk.Button(body, text='Restart sensor reader', command=restart).pack(fill='x', pady=4)
    ttk.Button(body, text='Advanced: choose another sensor library…', command=choose).pack(fill='x', pady=4)
    ttk.Button(body, text='Refresh status', command=refresh).pack(fill='x', pady=4)
    ttk.Button(body, text='Close', command=dialog.destroy).pack(anchor='e', pady=4)
    refresh()
