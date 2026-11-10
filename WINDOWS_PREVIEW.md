# Windows 11 RGB preview

Experimental source preview based on the Linux 0.5.0 release. Windows and physical-hub verification are pending. Keep the official controller closed while testing; use one running copy of Umbra Control.

## Setup (PowerShell in the extracted folder)

Python 3.12 (64-bit) with Tk is required. Create an isolated environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-windows.txt
.\.venv\Scripts\python.exe windows_diagnostics.py
```

This first diagnostic enumerates only matching Umbra interfaces (VID 1A86 / PID FE05); it does not send control commands. Share the output if the interface count is not exactly one.

Next, query status and LED counts without changing RGB mode or motor settings:

```powershell
.\.venv\Scripts\python.exe windows_diagnostics.py --probe
```

If the probe passes and LED counts match your setup, launch:

```powershell
.\.venv\Scripts\python.exe asiahorse_gui.py
```

Start with a solid color. Check RGB layout, port identification (after applying RGB once), effects and configuration export/import afterwards. Quit exits; the window close button minimizes the app. Running the app as administrator should not be necessary. Do not replace the device's standard Windows HID driver with Zadig/libusb.

## Scope

- Reuses RGB effects, layout, fan-group drawings, port identification and configuration sharing.
- Windows uses `hidapi`; Linux retains direct hidraw I/O without this dependency.
- Motor control, temperature/RPM sensors and login startup are disabled in this Windows preview. No fan-control commands are sent by its RGB worker.
- Imported fan profiles can be saved/exported but cannot be activated. Without local sensors their mappings remain empty.
- Single-instance locking is per local user. It cannot prevent the official app or another controller from opening the same hub.
- Configuration uses `~/.config/umbra-control` by default, as on Linux (or `XDG_CONFIG_HOME` if set).
- No Windows installer or signed executable is included yet. Do not use the Linux `install_desktop.py` on Windows.

HIDAPI reference: https://github.com/trezor/cython-hidapi
