"""Native Windows entry point. Self-test never opens the physical hub."""
import json
from pathlib import Path
import sys
import traceback


def self_test(output):
    result={'passed':False,'hardware_tested':False}
    try:
        import tkinter as tk
        import hid
        import asiahorse_gui, fan_ui, rgb_layout_ui, transfer_ui
        from windows_icon import set_native_icons
        import windows_sensors
        import windows_setup
        root=tk.Tk()
        try:
            root.title('Umbra packaging self-test')
            icon=Path(__file__).with_name('umbra-icon.ico')
            root.iconbitmap(default=str(icon))
            root.update()
            set_native_icons(root,icon)
            image=tk.PhotoImage(file=str(Path(__file__).with_name('umbra-icon.png')))
            assert image.width()>0
        finally:root.destroy()
        command=windows_sensors.helper_command('unused-in-self-test')
        if getattr(sys, 'frozen', False) and windows_setup.bundled_library() is None:
            raise RuntimeError('Bundled sensor library missing')
        result.update(passed=True,frozen=bool(getattr(sys,'frozen',False)),helper=command[0])
    except Exception:
        result['error']=traceback.format_exc()
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['passed'] else 1


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        raise SystemExit(self_test(sys.argv[2]))
    if sys.argv[1:]==['--create-shortcut']:
        import tkinter as tk
        from tkinter import messagebox
        from windows_shortcut import create
        root=tk.Tk();root.withdraw()
        try:
            create();messagebox.showinfo('Umbra Control','Desktop shortcut created.',parent=root)
        except Exception as exc:
            messagebox.showerror('Umbra Control',str(exc),parent=root)
        finally:root.destroy()
        raise SystemExit(0)
    from windows_launcher import main
    raise SystemExit(main())
