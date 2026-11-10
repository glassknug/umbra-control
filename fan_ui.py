"""Fan curves tab: editable curves, profile shortcuts and live history."""
from collections import deque
import queue
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from fan_curves import load_profiles, save_profiles, sensor_id, validate_points, validate_profile
from sensors import cpu_temperature, read_sensors
import startup


class FanTab:
    def __init__(self, root, frame, player):
        self.windows = sys.platform == "win32"
        self.root, self.player = root, player
        self.history = deque(maxlen=120)
        self.sensor_map = {}
        self.profiles = []
        self.name = tk.StringVar(value='Balanced')
        self.sensor = tk.StringVar()
        self.shortcut = tk.StringVar(value='1')
        self.points = tk.StringVar(value='35:50, 60:75, 80:100' if self.windows else '35:75, 60:85, 80:100')
        self.manual = tk.DoubleVar(value=100)
        self.start_at_login = tk.BooleanVar(value=False)
        self.state = tk.StringVar(value='Inactive · opening this tab does not change fan speed')
        self.current = tk.StringVar(value='Temperature: —    Requested fan duty: —')
        self.cpu_value = tk.StringVar(value='— °C')
        self.cpu_source = tk.StringVar(value='Detecting CPU sensor…')
        self.profile_choice = tk.StringVar()
        self.drag_index = None
        self.temp = None
        self.duty = None
        self.active_sensor = None
        self.pending_startup_sensor = None
        ttk.Label(frame, text='Fan curves · all hub fans', font=('Sans', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Duty is a requested percentage, not measured RPM. Curves continue while the app is minimized.', wraplength=780).pack(anchor='w', pady=5)
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=4)
        self.profile_box = ttk.Combobox(row, textvariable=self.profile_choice, state='readonly', width=23)
        self.profile_box.pack(side='left')
        self.profile_box.bind('<<ComboboxSelected>>', lambda _: self.load_selected())
        ttk.Button(row, text='New', command=self.new).pack(side='left', padx=4)
        ttk.Button(row, text='Save profile', command=self.save).pack(side='left')
        ttk.Button(row, text='Delete', command=self.delete).pack(side='left', padx=4)
        editor = ttk.Frame(frame)
        editor.pack(fill='x')
        ttk.Label(editor, text='Name').grid(row=0, column=0, sticky='w')
        ttk.Entry(editor, textvariable=self.name, width=23).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Label(editor, text='Ctrl+Alt+').grid(row=0, column=2)
        ttk.Combobox(editor, textvariable=self.shortcut, values=('', *map(str, range(1, 10))), state='readonly', width=3).grid(row=0, column=3)
        ttk.Label(editor, text='Sensor').grid(row=1, column=0, sticky='w', pady=6)
        self.sensor_box = ttk.Combobox(editor, textvariable=self.sensor, state='readonly', width=48)
        self.sensor_box.grid(row=1, column=1, columnspan=3, sticky='ew', padx=6)
        ttk.Button(editor, text='Refresh sensors', command=self.refresh_sensors).grid(row=1, column=4, padx=5)
        editor.columnconfigure(1, weight=1)
        cpu_card = tk.Frame(frame, bg='#202737', padx=16, pady=10)
        cpu_card.pack(fill='x', pady=(8, 6))
        tk.Label(cpu_card, text='CPU TEMPERATURE', bg='#202737', fg='#bbc5d7',
                 font=('Sans', 10, 'bold')).pack(side='left', padx=(0, 20))
        self.cpu_display = tk.Label(cpu_card, textvariable=self.cpu_value,
                                    bg='#202737', fg='#71e6cf', font=('Sans', 30, 'bold'))
        self.cpu_display.pack(side='left')
        tk.Label(cpu_card, textvariable=self.cpu_source, bg='#202737', fg='#bbc5d7',
                 justify='left', font=('Sans', 10)).pack(side='left', padx=20)
        ttk.Label(frame, text='Points: temperature °C : fan %. Drag points or edit below, then Apply curve.').pack(anchor='w', pady=(5, 0))
        self.chart = tk.Canvas(frame, height=195, bg='#202737', highlightthickness=0)
        self.chart.pack(fill='x', pady=4)
        self.chart.bind('<Configure>', lambda _: self.draw_curve())
        self.chart.bind('<Button-1>', self.pick)
        self.chart.bind('<B1-Motion>', self.drag)
        self.chart.bind('<ButtonRelease-1>', lambda _: setattr(self, 'drag_index', None))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.points).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Preview', command=self.preview).pack(side='left', padx=5)
        ttk.Button(row, text='Apply curve', command=self.apply).pack(side='left')
        ttk.Checkbutton(frame, text='Start minimized and apply this curve at login',
                        variable=self.start_at_login, command=self.set_startup).pack(anchor='w', pady=5)
        ttk.Label(frame, text='Windows startup runs with administrator privileges for CPU sensor access, 30 seconds after login. Run as administrator to enable or disable it.' if self.windows else 'Uses a saved curve snapshot. Reapply to update it; uncheck to disable.', wraplength=780).pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=8)
        ttk.Label(row, text='Manual %').pack(side='left')
        ttk.Spinbox(row, from_=50 if self.windows else 30, to=100, increment=1, textvariable=self.manual, width=6).pack(side='left', padx=5)
        ttk.Button(row, text='Apply manual', command=self.apply_manual).pack(side='left')
        ttk.Button(row, text='Stop curve / 100%', command=self.full).pack(side='left', padx=5)
        ttk.Label(frame, textvariable=self.state, wraplength=780).pack(anchor='w')
        ttk.Label(frame, textvariable=self.current).pack(anchor='w', pady=3)
        ttk.Label(frame, text='Live history · cyan: temperature °C · purple: requested duty % · last 120 samples').pack(anchor='w')
        self.live = tk.Canvas(frame, height=135, bg='#202737', highlightthickness=0)
        self.live.pack(fill='both', expand=True, pady=4)
        self.live.bind('<Configure>', lambda _: self.draw_history())
        ttk.Label(frame, text='Sensor error or ≥85 °C → request 100%. Increases are immediate; decreases are limited to 2%/s.\nNormal exit requests 100%; crash, sleep or USB loss cannot guarantee cooling recovery.\n50–100% on Windows; 30–100% on Linux. Only 75% and 100% have been hardware-tested. Shortcuts work while this app has focus.', wraplength=780).pack(anchor='w')
        self.refresh_sensors()
        try:
            self.profiles = load_profiles()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Profiles', f'Could not load profiles: {exc}', parent=root)
        self.update_choices()
        try:
            self.start_at_login.set(startup.load() is not None)
        except (OSError, ValueError):
            pass
        for key in range(1, 10):
            root.bind(f'<Control-Alt-KeyPress-{key}>', lambda _, key=str(key): self.activate_shortcut(key))
        self.poll()
        self.refresh_cpu()

    def refresh_cpu(self):
        if self.pending_startup_sensor:
            self.refresh_sensors()
            selected=next((label for label,identity in self.sensor_map.items() if identity==self.pending_startup_sensor),None)
            if selected:
                self.sensor.set(selected)
                self.pending_startup_sensor=None
        import math
        sensor = cpu_temperature(read_sensors())
        value = sensor.value if sensor else None
        valid = value is not None and math.isfinite(value) and -20 <= value <= 130
        self.cpu_value.set(f'{value:.1f} °C' if valid else '— °C')
        source = f'{sensor.source} · {sensor.label}' if sensor else 'No recognized CPU sensor'
        self.cpu_source.set(source + ('\nLive reading · updates every second' if valid else '\nCPU reading unavailable'))
        self.cpu_display.configure(fg='#efb16b' if valid and value >= 85 else '#71e6cf' if valid else '#bbc5d7')
        self.root.after(1000, self.refresh_cpu)

    def parse(self):
        return validate_points([tuple(map(float, item.strip().split(':'))) for item in self.points.get().split(',')])

    def preview(self):
        try:
            self.parse()
            self.draw_curve()
        except ValueError as exc:
            messagebox.showerror('Curve', str(exc), parent=self.root)

    def snapshot(self):
        return validate_profile(dict(name=self.name.get(), sensor=self.sensor_map.get(self.sensor.get(), ''),
                                     shortcut=self.shortcut.get(), points=self.parse()))

    def update_choices(self):
        self.profile_box.configure(values=[p['name'] for p in self.profiles])

    def save(self):
        try:
            p = self.snapshot()
            profiles = [x for x in self.profiles if x['name'] != p['name']] + [p]
            save_profiles(profiles)
            self.profiles = profiles
            self.profile_choice.set(p['name'])
            self.update_choices()
            self.state.set('Profile saved · press Apply curve to activate')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Profile', str(exc), parent=self.root)

    def delete(self):
        name = self.profile_choice.get()
        if not name:
            return
        if not messagebox.askyesno('Delete profile', f'Delete {name}? Active control continues until changed.', parent=self.root):
            return
        try:
            profiles = [p for p in self.profiles if p['name'] != name]
            save_profiles(profiles)
            self.profiles = profiles
            self.profile_choice.set('')
            self.update_choices()
        except OSError as exc:
            messagebox.showerror('Profile', str(exc), parent=self.root)

    def new(self):
        self.profile_choice.set('')
        self.name.set('New profile')
        self.shortcut.set('')
        self.points.set('35:50, 60:75, 80:100' if self.windows else '35:75, 60:85, 80:100')
        self.draw_curve()

    def load_selected(self):
        p = next((p for p in self.profiles if p['name'] == self.profile_choice.get()), None)
        if not p:
            return
        self.name.set(p['name'])
        self.shortcut.set(p['shortcut'])
        self.points.set(', '.join(f'{t:g}:{v:g}' for t, v in p['points']))
        self.sensor.set(next((label for label, identity in self.sensor_map.items() if identity == p['sensor']), ''))
        self.draw_curve()

    def activate_shortcut(self, key):
        p = next((p for p in self.profiles if p['shortcut'] == key), None)
        if p:
            self.profile_choice.set(p['name'])
            self.load_selected()
            self.apply()
        return 'break'

    def refresh_sensors(self):
        current = self.sensor_map.get(self.sensor.get())
        self.sensor_map = {}
        for s in read_sensors():
            if s.kind == 'temperature':
                label = f'{s.source} · {s.label} · {s.key if self.windows else s.key.split("/")[-2]}'
                self.sensor_map[label] = sensor_id(s)
        self.sensor_box.configure(values=list(self.sensor_map))
        chosen = next((label for label, identity in self.sensor_map.items() if identity == current), None)
        if chosen:
            self.sensor.set(chosen)
        elif current is not None:
            self.sensor.set('')
        elif not self.sensor.get():
            self.sensor.set(next((label for label in self.sensor_map if 'k10temp · Tctl' in label), ''))

    def set_startup(self):
        try:
            startup.configure(self.snapshot() if self.start_at_login.get() else None)
            self.state.set('Startup curve saved · starts minimized 30 seconds after Windows login' if self.windows and self.start_at_login.get() else 'Startup curve saved' if self.start_at_login.get() else 'Startup disabled')
        except (OSError, ValueError) as exc:
            try:self.start_at_login.set(startup.load() is not None)
            except (OSError,ValueError):self.start_at_login.set(False)
            messagebox.showerror('Startup', str(exc), parent=self.root)

    def start_saved(self):
        try:
            p = startup.load()
            if p:
                self.player.fan_curve(p['points'], p['sensor'])
                self.active_sensor = p['sensor']
                self.pending_startup_sensor = p['sensor']
                self.name.set(p['name'])
                self.shortcut.set(p['shortcut'])
                self.points.set(', '.join(f'{t:g}:{v:g}' for t,v in p['points']))
                self.draw_curve()
                self.state.set(f'Startup curve: {p["name"]}')
        except (OSError, ValueError) as exc:
            self.player.fan_full()
            messagebox.showerror('Startup curve', f'{exc}\nRequested 100%.', parent=self.root)

    def apply(self):
        try:
            p = self.snapshot()
            self.player.fan_curve(p['points'], p['sensor'])
            self.active_sensor = p['sensor']
            if self.start_at_login.get():
                startup.configure(p)
            self.state.set(f'Activating curve: {p["name"]} · unsaved edits require Save profile to persist')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Fan control', str(exc), parent=self.root)

    def apply_manual(self):
        try:
            self.player.fan_manual(self.manual.get())
            self.active_sensor = None
            self.state.set('Applying manual duty…')
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror('Fan control', str(exc), parent=self.root)

    def full(self):
        self.player.fan_full()
        self.active_sensor = None
        self.state.set('Stopping curve and requesting 100%…')

    def axes(self, canvas, title):
        canvas.delete('all')
        w, h = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 100)
        for value in range(0, 101, 25):
            y = h - 24 - value / 100 * (h - 48)
            canvas.create_line(40, y, w - 22, y, fill='#35405a')
            canvas.create_text(22, y, text=str(value), fill='#bbc5d7')
        canvas.create_text(w / 2, 11, text=title, fill='#e9eef8')
        return w, h

    def draw_curve(self):
        w, h = self.axes(self.chart, 'Fan duty % · temperature 0–100 °C →')
        try:
            points = self.parse()
        except ValueError:
            return
        coords = []
        for t, v in points:
            x, y = 40 + t / 100 * (w - 62), h - 24 - v / 100 * (h - 48)
            coords.extend((x, y))
        self.chart.create_line(40, coords[1], *coords, w - 22, coords[-1], fill='#aa89ff', width=3)
        for i in range(0, len(coords), 2):
            x, y = coords[i:i+2]
            self.chart.create_oval(x-5, y-5, x+5, y+5, fill='#71e6cf', outline='')
        emergency_x = 40 + 0.85 * (w - 62)
        self.chart.create_line(emergency_x, 24, emergency_x, h - 24, fill='#efb16b', dash=(4, 3))
        self.chart.create_text(emergency_x - 4, h - 38, text='85 °C → 100%', anchor='e', fill='#efb16b')
        for t in range(0, 101, 20):
            self.chart.create_text(40+t/100*(w-62), h-10, text=str(t), fill='#bbc5d7')

    def pick(self, event):
        try:
            points = self.parse()
        except ValueError:
            return
        w, h = self.chart.winfo_width(), self.chart.winfo_height()
        distances = [((40+t/100*(w-62)-event.x)**2 + (h-24-v/100*(h-48)-event.y)**2, i) for i, (t,v) in enumerate(points)]
        distance, index = min(distances)
        self.drag_index = index if distance < 400 else None

    def drag(self, event):
        if self.drag_index is None:
            return
        points = list(self.parse())
        i = self.drag_index
        w, h = self.chart.winfo_width(), self.chart.winfo_height()
        low_t = points[i-1][0]+1 if i else 0
        high_t = points[i+1][0]-1 if i+1 < len(points) else 100
        low_v = points[i-1][1] if i else 30
        high_v = points[i+1][1] if i+1 < len(points) else 100
        if low_t > high_t:
            return
        points[i] = (round(max(low_t, min(high_t, (event.x-40)/(w-62)*100))),
                     round(max(low_v, min(high_v, (h-24-event.y)/(h-48)*100))))
        self.points.set(', '.join(f'{t:g}:{v:g}' for t, v in points))
        self.draw_curve()

    def draw_history(self):
        w, h = self.axes(self.live, '°C / % · one sample per second while control is active')
        for column, color in ((0, '#71e6cf'), (1, '#aa89ff')):
            segment = []
            for i, item in enumerate(self.history):
                value = item[column]
                if value is None:
                    if len(segment) >= 4:
                        self.live.create_line(*segment, fill=color, width=2)
                    segment = []
                    continue
                segment.extend((40+i/119*(w-62), h-24-max(0,min(100,value))/100*(h-48)))
            if len(segment) >= 4:
                self.live.create_line(*segment, fill=color, width=2)

    def poll(self):
        changed = False
        try:
            while True:
                sample = self.player.fan_events.get_nowait()
                self.temp, self.duty = sample['temperature'], sample['duty']
                self.state.set(sample['mode'])
                t = '—' if self.temp is None else f'{self.temp:.1f} °C'
                p = '—' if self.duty is None else f'{self.duty}%'
                self.current.set(f'Temperature: {t}    Requested fan duty: {p} (not RPM)')
                self.history.append((self.temp, self.duty))
                changed = True
        except queue.Empty:
            pass
        if changed:
            self.draw_history()
        self.root.after(200, self.poll)

