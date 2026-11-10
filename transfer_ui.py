"""Review configuration JSON and map imported sensors without activating control."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config_transfer import export_bundle, import_bundle, read_bundle, suggested_sensors, write_bundle
from fan_curves import sensor_id, load_profiles
from sensors import read_sensors


class TransferTab:
    def __init__(self,root,frame,rgb_tab,fan_tab):
        self.root,self.rgb_tab,self.fan_tab=root,rgb_tab,fan_tab
        self.bundle=None;self.sensor_vars={};self.sensor_map={}
        self.status=tk.StringVar(value='Export a JSON file or choose a file to preview before importing.')
        ttk.Label(frame,text='Export/Import',font=('Sans',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Share your RGB layout and saved fan profiles as a configuration file.',wraplength=780).pack(anchor='w',pady=8)
        ttk.Label(frame,text='Export includes the current RGB layout and saved fan profiles. Save fan profiles in Fan curves first.\nAutostart, running control, local paths and account information are not exported.',wraplength=780).pack(anchor='w',pady=5)
        ttk.Button(frame,text='Export configuration…',command=self.export).pack(anchor='w',pady=8)
        ttk.Separator(frame).pack(fill='x',pady=10)
        ttk.Button(frame,text='Choose configuration to import…',command=self.preview).pack(anchor='w',pady=5)
        self.summary=tk.StringVar(value='No file selected')
        ttk.Label(frame,textvariable=self.summary,wraplength=780).pack(anchor='w',pady=8)
        self.mappings=ttk.Frame(frame);self.mappings.pack(fill='x')
        ttk.Label(frame,text='Review each temperature sensor. Unmapped profiles remain inactive until you select a sensor.\nPort numbers may need adjustment to match your physical wiring.',wraplength=780).pack(anchor='w',pady=8)
        ttk.Label(frame,text='Import replaces saved RGB layout and saved fan profiles. A backup is made first.\nIt does not change running RGB/fan control or your login-startup settings.',wraplength=780,foreground='#efb16b').pack(anchor='w',pady=8)
        self.import_button=ttk.Button(frame,text='Import reviewed configuration',command=self.apply,state='disabled')
        self.import_button.pack(anchor='w',pady=8)
        ttk.Label(frame,textvariable=self.status,wraplength=780).pack(anchor='w',pady=6)

    def export(self):
        try:
            if not self.rgb_tab.update_selected():return
            layout=dict(version=1,devices=self.rgb_tab.devices)
            profiles=self.fan_tab.profiles if self.fan_tab is not None else load_profiles()
            bundle=export_bundle(layout,profiles,read_sensors())
            filename=filedialog.asksaveasfilename(parent=self.root,title='Export Umbra configuration',defaultextension='.json',filetypes=[('Umbra configuration','*.json')],initialfile='umbra-configuration.json')
            if not filename:return
            write_bundle(filename,bundle)
            self.status.set(f'Exported {len(bundle["rgb_layout"]["devices"])} RGB groups and {len(bundle["fan_profiles"])} fan profiles.')
        except (OSError,ValueError) as exc:messagebox.showerror('Export configuration',str(exc),parent=self.root)

    def preview(self):
        filename=filedialog.askopenfilename(parent=self.root,title='Preview Umbra configuration',filetypes=[('Umbra configuration','*.json')])
        if not filename:return
        self.bundle=None;self.import_button.configure(state='disabled')
        for child in self.mappings.winfo_children():child.destroy()
        self.sensor_vars={}
        try:
            bundle=read_bundle(filename)
            sensors=read_sensors()
            self.sensor_map={'Unmapped — select later':''}
            for s in sensors:
                if s.kind=='temperature':self.sensor_map[f'{s.source} · {s.label} · {s.key}']=sensor_id(s)
            suggested=suggested_sensors(bundle,sensors)
            for row,p in enumerate(bundle['fan_profiles']):
                ttk.Label(self.mappings,text=p['name']).grid(row=row,column=0,sticky='w',padx=(0,12),pady=3)
                var=tk.StringVar(value=next((label for label,identity in self.sensor_map.items() if identity==suggested[p['name']]),'Unmapped — select later'))
                self.sensor_vars[p['name']]=var
                ttk.Combobox(self.mappings,textvariable=var,values=list(self.sensor_map),state='readonly',width=50).grid(row=row,column=1,sticky='ew',pady=3)
            self.mappings.columnconfigure(1,weight=1)
            names=', '.join(p['name'] for p in bundle['fan_profiles']) or 'none'
            self.summary.set(f'RGB port groups: {len(bundle["rgb_layout"]["devices"])}\nFan profiles: {names}')
            self.bundle=bundle;self.import_button.configure(state='normal')
            self.status.set('Preview loaded. Review sensor mappings and import only when ready.')
        except (OSError,ValueError) as exc:
            self.summary.set('Invalid configuration; nothing imported')
            messagebox.showerror('Import preview',str(exc),parent=self.root)

    def apply(self):
        if self.bundle is None:return
        if not messagebox.askyesno('Replace saved configuration?','Replace saved RGB layout and fan profiles, including unsaved editor contents?\n\nA backup will be created. Running control and login-startup settings stay as they are.',parent=self.root):return
        try:
            mappings={name:self.sensor_map[var.get()] for name,var in self.sensor_vars.items()}
            profiles,backup=import_bundle(self.bundle,mappings,read_sensors())
            self.rgb_tab.devices=self.bundle['rgb_layout']['devices']
            self.rgb_tab.dirty=False;self.rgb_tab.refresh_choices()
            self.rgb_tab.select(0 if self.rgb_tab.devices else None)
            self.rgb_tab.status.set('Imported layout · press Apply layout RGB when ready')
            if self.fan_tab is not None:
                self.fan_tab.profiles=profiles;self.fan_tab.update_choices()
                self.fan_tab.profile_choice.set(profiles[0]['name'] if profiles else '')
                self.fan_tab.refresh_sensors()
                if profiles:self.fan_tab.load_selected()
                else:self.fan_tab.new()
            self.status.set(f'Imported. Nothing activated. Backup saved in {backup}')
            self.import_button.configure(state='disabled');self.bundle=None
        except (OSError,ValueError,KeyError) as exc:messagebox.showerror('Import configuration',str(exc),parent=self.root)
