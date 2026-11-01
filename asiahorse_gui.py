#!/usr/bin/env python3
"""Native desktop RGB control and read-only Linux sensor monitoring."""
import queue
import sys
from pathlib import Path

from sensors import read_sensors
from effects import EFFECTS, Player, Settings


def main():
    try:
        import tkinter as tk
        from tkinter import colorchooser, messagebox, ttk
    except ImportError as exc:
        print(f"Tk is unavailable: {exc}\nInstall Python Tk: python3-tkinter on Bazzite/Fedora; python3-tk on Debian/Ubuntu.", file=sys.stderr)
        return 1

    import fcntl
    import os
    lock_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "umbra-control"
    lock_dir.mkdir(parents=True, exist_ok=True)
    session_lock = (lock_dir / "session.lock").open("a")
    try:
        fcntl.flock(session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Umbra Control is already running. Restore its minimized window.", file=sys.stderr)
        return 0

    root = tk.Tk(className="Asiahorse-umbra")
    icon_path = Path(__file__).with_name("umbra-icon.png")
    if icon_path.is_file():
        root.app_icon = tk.PhotoImage(file=str(icon_path))
        root.iconphoto(True, root.app_icon)
    root.title("Umbra Control for Linux")
    root.geometry(f"940x{min(940, root.winfo_screenheight() - 90)}")
    root.minsize(860, min(860, root.winfo_screenheight() - 110))
    root.configure(bg="#151923")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#151923")
    style.configure("TLabel", background="#151923", foreground="#e9eef8", font=("Sans", 11))
    style.configure("Title.TLabel", font=("Sans", 23, "bold"))
    style.configure("TButton", padding=9, font=("Sans", 11))
    style.configure("Treeview", background="#202737", fieldbackground="#202737", foreground="#e9eef8", rowheight=30)
    style.configure("Treeview.Heading", font=("Sans", 10, "bold"))

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    header = ttk.Frame(frame)
    header.pack(fill="x")
    ttk.Label(header, text="Umbra Control", style="Title.TLabel").pack(side="left")

    def about():
        messagebox.showinfo(
            "About Umbra Control for Linux",
            "Umbra Control for Linux · 0.4.0 preview\n\n"
            "Project by glassknug.\n"
            "Desktop GUI, RGB effects, USB fan-control command analysis and hardware testing, "
            "temperature curves, profiles, graphs, shortcuts and menu launcher.\n\n"
            "Original Linux HID driver: ToeTagger / LuxDev372.\n"
            "Earlier RGB protocol research: maihcx and u/idk_a_name_wtf.\n\n"
            "Independent community project; not an official AsiaHorse application.\n"
            "MIT licensed. Original copyright and license notices are preserved.",
            parent=root,
        )

    ttk.Button(header, text="About", command=about).pack(side="right")
    ttk.Label(frame, text="Lighting and system monitoring").pack(anchor="w", pady=(3, 20))
    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True, pady=(0, 6))
    lighting = ttk.Frame(notebook, padding=12)
    fan_container = ttk.Frame(notebook)
    fan_canvas = tk.Canvas(fan_container, bg="#151923", highlightthickness=0)
    fan_scroll = ttk.Scrollbar(fan_container, orient="vertical", command=fan_canvas.yview)
    fan_canvas.configure(yscrollcommand=fan_scroll.set)
    fan_scroll.pack(side="right", fill="y")
    fan_canvas.pack(side="left", fill="both", expand=True)
    fans = ttk.Frame(fan_canvas, padding=12)
    fan_window = fan_canvas.create_window(0, 0, anchor="nw", window=fans)
    fans.bind("<Configure>", lambda _: fan_canvas.configure(scrollregion=fan_canvas.bbox("all")))
    fan_canvas.bind("<Configure>", lambda e: fan_canvas.itemconfigure(fan_window, width=e.width))
    notebook.add(lighting, text="RGB & sensors")
    notebook.add(fan_container, text="Fan curves")
    layout_container = ttk.Frame(notebook)
    layout_canvas = tk.Canvas(layout_container, bg="#151923", highlightthickness=0)
    layout_scroll = ttk.Scrollbar(layout_container, orient="vertical", command=layout_canvas.yview)
    layout_canvas.configure(yscrollcommand=layout_scroll.set)
    layout_scroll.pack(side="right", fill="y")
    layout_canvas.pack(side="left", fill="both", expand=True)
    control_container = ttk.Frame(layout_canvas, padding=12)
    layout_window = layout_canvas.create_window(0, 0, anchor="nw", window=control_container)
    control_container.bind("<Configure>", lambda _: layout_canvas.configure(scrollregion=layout_canvas.bbox("all")))
    layout_canvas.bind("<Configure>", lambda e: layout_canvas.itemconfigure(layout_window, width=e.width))
    notebook.add(layout_container, text="RGB layout")
    frame = lighting
    ttk.Label(frame, text="Lighting · all connected RGB ports").pack(anchor="w")
    effect = tk.StringVar(value=EFFECTS[0])
    ttk.Label(frame, text="Effect").pack(anchor="w", pady=(10, 3))
    ttk.Combobox(frame, textvariable=effect, values=EFFECTS, state="readonly").pack(fill="x")
    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=12)
    selected = tk.StringVar(value="#71e6cf")
    brightness = tk.DoubleVar(value=70)
    swatch = tk.Label(controls, text="   ", bg=selected.get(), width=6, height=2)
    swatch.pack(side="left", padx=(0, 10))

    def choose():
        _, color = colorchooser.askcolor(color=selected.get(), parent=root, title="Choose RGB color")
        if color:
            selected.set(color)
            swatch.configure(bg=color)

    ttk.Button(controls, text="Choose color…", command=choose).pack(side="left")
    ttk.Label(controls, textvariable=selected).pack(side="left", padx=12)
    ttk.Label(frame, text="Brightness").pack(anchor="w")
    ttk.Scale(frame, from_=0, to=100, variable=brightness).pack(fill="x", pady=6)
    speed = tk.DoubleVar(value=1)
    ttk.Label(frame, text="Speed · slow → fast (0.25–3×)").pack(anchor="w")
    ttk.Scale(frame, from_=0.25, to=3, variable=speed).pack(fill="x", pady=6)
    ttk.Label(frame, text="Selected color applies to solid color, breathing and chase.").pack(anchor="w")
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=8)
    player = Player()

    def send():
        color = selected.get().lstrip("#")
        rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
        player.start(Settings(effect.get(), rgb, brightness.get() / 100, speed.get()))
        status.set("Starting effect…")

    ttk.Button(actions, text="Start / apply", command=send).pack(side="left")
    ttk.Button(actions, text="Stop", command=player.stop).pack(side="left", padx=10)
    ttk.Button(actions, text="Turn off RGB", command=player.off).pack(side="left")
    status = tk.StringVar(value="Choose an effect and press Start / apply. Press again to apply changes.")
    ttk.Label(frame, textvariable=status, wraplength=760).pack(anchor="w", pady=(0, 18))
    ttk.Label(frame, text="Temperatures and fan speeds").pack(anchor="w")
    ttk.Label(frame, text="Linux hwmon · sensor names do not correspond to hub RGB ports", wraplength=760).pack(anchor="w", pady=5)
    table_frame = ttk.Frame(frame)
    table_frame.pack(fill="both", expand=True)
    table = ttk.Treeview(table_frame, columns=("source", "sensor", "value"), show="headings")
    for column, title, width in (("source", "Source", 220), ("sensor", "Sensor", 260), ("value", "Value", 130)):
        table.heading(column, text=title)
        table.column(column, width=width, minwidth=90)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    table.pack(fill="both", expand=True)
    sensor_status = tk.StringVar()
    ttk.Label(frame, textvariable=sensor_status, wraplength=760).pack(anchor="w", pady=(8, 0))

    def refresh():
        try:
            while True:
                status.set(player.events.get_nowait())
        except queue.Empty:
            pass
        root.after(100, refresh)

    def close():
        player.close()
        # Keep Tk responsive while USB initialization is completing.
        status.set("Closing USB connection…")
        def wait_for_worker():
            if player.thread.is_alive():
                root.after(100, wait_for_worker)
            else:
                errors = []
                try:
                    while True:
                        event = player.events.get_nowait()
                        if "Could not request 100%" in event:
                            errors.append(event)
                except queue.Empty:
                    pass
                if errors:
                    messagebox.showerror("Check cooling", "\n".join(errors), parent=root)
                root.destroy()
        wait_for_worker()

    root.protocol("WM_DELETE_WINDOW", root.iconify)
    ttk.Button(header, text="Quit", command=close).pack(side="right", padx=6)

    def update_sensors():
        sensors = read_sensors()
        current = {sensor.key for sensor in sensors}
        for key in table.get_children():
            if key not in current:
                table.delete(key)
        for sensor in sensors:
            value = "Unavailable" if sensor.value is None else (
                f"{sensor.value:.1f} °C" if sensor.kind == "temperature" else f"{sensor.value:.0f} RPM")
            values = (sensor.source, sensor.label, value)
            if table.exists(sensor.key):
                table.item(sensor.key, values=values)
            else:
                table.insert("", "end", iid=sensor.key, values=values)
        sensor_status.set("Refreshes every two seconds · read-only" if sensors else
                          "No hwmon sensors found. Check your system sensor drivers.")
        root.after(2000, update_sensors)

    from fan_ui import FanTab
    fan_tab = FanTab(root, fans, player)
    from rgb_layout_ui import RGBLayoutTab
    control_tab = RGBLayoutTab(root, control_container, player, status)
    if "--autostart" in sys.argv:
        fan_tab.start_saved()
        root.after(100, root.iconify)
    refresh()
    update_sensors()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
