# Windows 11 preview: RGB, sensors and fan curves

Experimental source branch based on Linux 0.5.0. Windows RGB and manual motor requests have been tried by the owner. The new sensor backend, automatic curves, icon/shortcut and setup helper still require native Windows testing. 78 automated tests pass on the Linux development host, including simulated Windows sensor failures. Linux release/main is unchanged.

## Install/update

Quit an older running copy. Extract the complete branch ZIP to a permanent folder (shortcuts point there), then double-click **setup_windows.cmd**. Python 3.12 64-bit must already be installed. Setup creates a local `.venv`, installs binary wheels from `requirements-windows.txt` and creates **Umbra Control** on your actual Desktop (including redirected/OneDrive Desktops). A failed shortcut does not prevent use of `start_windows.cmd`.

Launch with that shortcut or `start_windows.cmd`; PowerShell can then be closed. Quit exits, and the window's close button minimizes. Logs: `%LOCALAPPDATA%\UmbraControl\windows.log`. Close AsiaHorse/SignalRGB and other controllers while testing.

## Sensor library setup

Windows CPU temperatures require a hardware sensor library; Python/Tk alone does not provide them. This preview reads the official **LibreHardwareMonitor** library through Python.NET in a separate child process. No LibreHardwareMonitor binaries are redistributed, no web server is enabled, and our helper only updates hardware and reads sensors. It never calls LHM fan-control APIs.

1. Download **LibreHardwareMonitor.zip** (the .NET Framework build, not the `.NET.10.zip` build) from the official [v0.9.6 release](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6).
2. Extract the **whole** ZIP and retain all DLLs, dependencies and license notices together. The folder must contain `LibreHardwareMonitorLib.dll`.
3. First run the official LibreHardwareMonitor application and confirm that a real CPU temperature is present. Follow its official driver setup if prompted. Some sensors require administrator privileges. Close its application after this check; it need not stay running for our library helper.
4. In Umbra Control, RGB & sensors, press **Choose sensor library folder…** and select that extracted folder. This loads executable .NET library code from the selected folder; select the official download only.
5. Wait for sensor values. If CPU values are unavailable, inspect the status message. The library helper inherits the app's privileges: if necessary, Quit and right-click `start_windows.cmd` → Run as administrator for a sensor test. RGB alone does not need elevation. No automatic elevation, driver install or security-setting changes are performed by Umbra.
6. To retry after fixing setup, use **Restart sensor reader**. The library path is stored locally in `%LOCALAPPDATA%\UmbraControl\sensor-directory.txt` and is not included in shared configurations.

To collect sensor-only diagnostics from PowerShell in the project folder (after choosing the library):

```powershell
.\.venv\Scripts\python.exe windows_diagnostics.py --sensors
```

That mode does not open the Umbra HID device or send motor commands. If testing an elevated app, run the diagnostic from an equivalently elevated terminal to compare sensor access.

## Curve test

First verify that the selected CPU reading tracks LibreHardwareMonitor. In **Fan curves**, use **Refresh sensors**, select that specific sensor, and start with `35:75, 60:85, 80:100`. Save the profile if desired, then Apply curve. Starting the app or choosing a library does not activate motor control.

- Windows requests and all curve points are restricted to **50–100%**. Existing imported curves below 50% must be edited before activation. Linux retains 30–100%.
- Missing, invalid or >=5-second-old samples, or a selected temperature >=85 °C, request 100%. CPU readings of zero are treated as unavailable. Check again within the worker's one-second control cycle.
- Increases are immediate; decreases are limited to 2 percentage points/second. A 100% to 75% transition takes roughly 13 seconds.
- Use **Stop sensor reader** while a curve is active: it should show unavailable and request 100%. Observe cooling; a requested duty is not proof of physical RPM.
- Quit requests 100% after motor control. Crash, sleep or USB loss cannot guarantee recovery. Login startup is available as an opt-in scheduled task; see below.
- Fan control is hub-wide, never individual per port. Imported profiles require local sensor mapping; nothing imported activates automatically.

## RGB diagnostics

```powershell
.\.venv\Scripts\python.exe windows_diagnostics.py
.\.venv\Scripts\python.exe windows_diagnostics.py --probe
```

Enumeration does not send commands. The probe queries status/topology without changing RGB mode or motor duty. The owner's initial topology only reported P3; after using the official app it reported P3=110, P4=16, P7=24, P8=24. Automatic device initialization is still under investigation. Use the actual returned LED counts; do not guess from fan count drawings. Keep the standard Windows HID driver; no Zadig/libusb driver replacement is needed.

## Credits and dependencies

Existing community driver/protocol credits remain in README.md and LICENSE. LibreHardwareMonitor is a separately downloaded, MPL-2.0 sensor dependency; retain its license and third-party notices. Python.NET is an MIT-licensed Python/.NET bridge. No Windows installer or signed standalone executable is included yet; do not use the Linux `install_desktop.py` on Windows.

- https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- https://pythonnet.github.io/pythonnet/python.html
- https://github.com/trezor/cython-hidapi

## CPU available in LHM but missing in Umbra

The sensor-only diagnostic waits up to 15 seconds for a valid CPU reading and prints the helper's actual elevation/bitness, library and PawnIO versions, read-only PawnIO device-open result, AMD module loaded state (best-effort reflection for the supported version) and raw CPU values. The probe opens/closes a device handle only; no IOCTL is sent by the access probe. These details are not exported with configurations. The helper initializes in the chosen library directory and adds that directory for dependency resolution. Do not interpret this diagnostic improvement as verified CPU compatibility.

## Taskbar icon and signing

Native small/large icons are now assigned to the mapped outer Tk window after startup, supplementing the .ico and AppUserModelID. This change has mocked API tests but still needs native taskbar verification; an already-pinned Python shortcut may retain its own icon. A future native executable must embed the same icon and version metadata and preserve the sensor helper subprocess behavior. The current preview is Python source and is not Authenticode-signed. See WINDOWS_SIGNING.md for signing options and requirements.

## Native EXE package (0.6.1 preview, unsigned)

`build_windows.cmd` builds on Windows with Python 3.12, using an isolated `.build-venv`. It creates `dist/UmbraControl-Windows-preview.zip` and a SHA256 sidecar. An equivalent Windows Actions workflow builds on pushes to the preview branch and uploads the archive as a test artifact. Each build smoke-tests the actual GUI EXE (Tk, imports and icons without opening HID) and helper EXE (.NET runtime import). These checks do not test a physical hub, CPU sensor or a clean Windows 11 installation.

Extract the whole native ZIP. Run `UmbraControl.exe` (right-click Run as administrator for CPU sensor access). `Create desktop shortcut.cmd` creates a shortcut targeting that branded executable. Python is bundled, but LibreHardwareMonitor/PawnIO remain separate prerequisites. User configuration and logs retain their locations. Signing is not performed; the SHA256 sidecar is an integrity checksum only.

## Windows login startup

After selecting and applying a valid local-sensor curve, check **Start minimized and apply this curve at login**. Run Umbra as administrator to enable or disable this feature. It stores a separate snapshot of the curve and registers `UmbraControl-<current-user-SID>` in the root Task Scheduler folder for that user only: interactive logon, highest privileges, a 30-second logon delay, no saved credentials, no runtime time limit and IgnoreNew for duplicate task launches. The app's existing per-user lock also prevents a second copy. Normal launches still do not activate curves automatically.

Reapply to update the snapshot. Unchecking removes this task and the startup snapshot. Manual duty changes do not disable the saved login curve. Move the package to a permanent folder before enabling; re-enable if you later move it. Config writes roll back if registration fails. Disabled/deleted tasks are not reported as enabled.

At login, missing or stale sensor data requests 100% until usable readings arrive. Test an actual sign-out/sign-in on Windows 11, wait about 30 seconds, restore the minimized app and confirm the saved curve/sensor. Then confirm unchecking prevents the next login launch. These login tests are not performed by CI. The previous high-level banner has been removed; preview/version details remain in About and package metadata.
