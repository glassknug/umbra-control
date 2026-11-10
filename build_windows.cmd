@echo off
setlocal
pushd "%~dp0"
py -3.12 -m venv .build-venv
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements-build-windows.txt
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" build_windows.py
if errorlevel 1 goto failed
echo Package ready in the dist folder. It is unsigned.
pause
popd
exit /b 0
:failed
echo Build failed. Please share the error above.
pause
popd
exit /b 1
