"""Launch without a console and preserve startup/callback errors in a local log."""
import contextlib
import os
from pathlib import Path
import traceback


def main():
    log_dir = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'UmbraControl'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'windows.log'
    # Keep the preceding log for troubleshooting without unbounded growth.
    if log_path.exists() and log_path.stat().st_size > 1024 * 1024:
        log_path.replace(log_dir / 'windows.previous.log')
    with log_path.open('a', encoding='utf-8', buffering=1) as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                from asiahorse_gui import main as run
                return run()
            except Exception:
                traceback.print_exc()
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk(); root.withdraw()
                messagebox.showerror('Umbra Control could not start', f'Startup failed. Details are saved in:\n{log_path}',parent=root)
                root.destroy()
                return 1


if __name__ == '__main__':
    raise SystemExit(main())
