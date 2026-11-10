@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Python environment not found. Follow WINDOWS_PREVIEW.md first.
    pause
    exit /b 1
)
start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0windows_launch.pyw"
