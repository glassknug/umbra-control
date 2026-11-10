@echo off
setlocal
pushd "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements-windows.txt
if errorlevel 1 goto failed
echo Setup complete. Start the app with start_windows.cmd.
".venv\Scripts\python.exe" windows_shortcut.py
echo See WINDOWS_PREVIEW.md for the official sensor library setup.
pause
popd
exit /b 0
:failed
echo Setup failed. Please share the error above.
pause
popd
exit /b 1
