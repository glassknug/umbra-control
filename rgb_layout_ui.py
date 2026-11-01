"""Draggable RGB port groups drawn directly in Tk; no proprietary art."""
import math
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

from effects import EFFECTS
from rgb_layout import KINDS, load_layout, placement, save_layout, scene_settings, validate_layout, fan_geometry

BG,PANEL,TEXT,MUTED,ACCENT='#151923','#202737','#e9eef8','#bbc5d7','#71e6cf'


class RGBLayoutTab:
    def __init__(self,root,frame,player,playback_status):
        self.root,self.player=root,player
        self.devices=[];self.selected=None;self.dragging=None;self.offset=(0,0);self.dirty=False
        self.choice=tk.StringVar();self.name=tk.StringVar();self.port=tk.StringVar();self.kind=tk.StringVar(value=KINDS[0])
        self.fan_count=tk.IntVar(value=1)
        self.orientation=tk.StringVar(value='Horizontal');self.color=tk.StringVar(value=ACCENT)
        self.effect=tk.StringVar(value=EFFECTS[0]);self.brightness=tk.DoubleVar(value=70);self.speed=tk.DoubleVar(value=1)
        self.status=tk.StringVar(value='Drag a device into the case. Editing the layout sends no commands.')
        self.topology=tk.StringVar(value='LED counts are read from the hub when RGB starts.')
        ttk.Label(frame,text='RGB layout · build your PC',font=('Sans',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Fans, LED strips and Strimer-style ARGB cables · one effect per hub port',wraplength=800).pack(anchor='w',pady=(3,4))
        ttk.Label(frame,textvariable=self.topology,foreground=MUTED,wraplength=810).pack(anchor='w')
        body=ttk.Frame(frame);body.pack(fill='both',expand=True,pady=8)
        self.canvas=tk.Canvas(body,bg=BG,highlightthickness=0,height=480,width=470)
        self.canvas.pack(side='left',fill='both',expand=True)
        side=ttk.Frame(body,padding=(12,0,0,0));side.pack(side='right',fill='y')
        ttk.Label(side,text='Selected RGB port group',font=('Sans',11,'bold')).pack(anchor='w')
        self.choices=ttk.Combobox(side,textvariable=self.choice,state='readonly',width=25)
        self.choices.pack(fill='x',pady=5);self.choices.bind('<<ComboboxSelected>>',self.select_choice)
        ttk.Label(side,text='Name').pack(anchor='w');self.name_entry=ttk.Entry(side,textvariable=self.name,width=25);self.name_entry.pack(fill='x',pady=3)
        ttk.Label(side,text='Hub port · match physical wiring').pack(anchor='w')
        self.port_box=ttk.Combobox(side,textvariable=self.port,values=list(map(str,range(1,11))),state='readonly',width=8);self.port_box.pack(fill='x',pady=3)
        ttk.Label(side,text='Shape / device type').pack(anchor='w')
        self.kind_box=ttk.Combobox(side,textvariable=self.kind,values=KINDS,state='readonly');self.kind_box.pack(fill='x',pady=3)
        self.orientation_box=ttk.Combobox(side,textvariable=self.orientation,values=('Horizontal','Vertical'),state='readonly');self.orientation_box.pack(fill='x',pady=3)
        self.count_row=ttk.Frame(side)
        ttk.Label(self.count_row,text='Fan count · daisy chain').pack(side='left')
        self.count_box=ttk.Spinbox(self.count_row,from_=1,to=10,increment=1,textvariable=self.fan_count,width=4,state='readonly')
        self.count_box.pack(side='right')
        self.kind.trace_add('write',lambda *_:self.show_fan_count())
        ttk.Label(side,text='Effect').pack(anchor='w')
        self.effect_box=ttk.Combobox(side,textvariable=self.effect,values=EFFECTS,state='readonly');self.effect_box.pack(fill='x',pady=3)
        self.color_button=ttk.Button(side,text='Choose color…',command=self.choose_color);self.color_button.pack(fill='x',pady=3)
        self.color_entry=ttk.Entry(side,textvariable=self.color);self.color_entry.pack(fill='x',pady=3)
        row=ttk.Frame(side);row.pack(fill='x',pady=4)
        ttk.Label(row,text='Brightness %').pack(side='left')
        self.brightness_box=ttk.Spinbox(row,from_=0,to=100,textvariable=self.brightness,width=6);self.brightness_box.pack(side='right')
        row=ttk.Frame(side);row.pack(fill='x',pady=4)
        ttk.Label(row,text='Effect speed ×').pack(side='left')
        self.speed_box=ttk.Spinbox(row,from_=.25,to=3,increment=.25,textvariable=self.speed,width=6);self.speed_box.pack(side='right')
        self.update_button=ttk.Button(side,text='Update selected device',command=self.update_selected);self.update_button.pack(fill='x',pady=3)
        self.remove_button=ttk.Button(side,text='Remove selected device',command=self.remove);self.remove_button.pack(fill='x',pady=3)
        ttk.Separator(side).pack(fill='x',pady=8)
        ttk.Button(side,text='Apply layout RGB',command=self.apply).pack(fill='x',pady=3)
        ttk.Button(side,text='Stop RGB animation',command=self.stop).pack(fill='x',pady=3)
        ttk.Button(side,text='Turn off ALL RGB',command=player.off).pack(fill='x',pady=3)
        ttk.Label(side,text='Apply replaces current RGB.\nUnassigned hub ports turn dark.\nFan motor curves are unchanged.',foreground='#efb16b').pack(anchor='w',pady=6)
        tools=ttk.Frame(frame);tools.pack(fill='x')
        self.add_kind=tk.StringVar(value=KINDS[0])
        ttk.Combobox(tools,textvariable=self.add_kind,values=KINDS,state='readonly',width=12).pack(side='left')
        ttk.Button(tools,text='Add device',command=lambda:self.add(self.add_kind.get())).pack(side='left',padx=5)
        ttk.Button(tools,text='Save layout',command=self.save).pack(side='left')
        ttk.Label(frame,textvariable=self.status,wraplength=810).pack(anchor='w',pady=4)
        ttk.Label(frame,textvariable=playback_status,wraplength=810,foreground=MUTED).pack(anchor='w',pady=3)
        ttk.Label(frame,text='ARGB cables must be compatible with the Umbra ARGB output. Separate USB controllers are not supported.\nOne icon represents a port / LED chain; connected devices sharing that port share its effect. Geometry is an illustration.',wraplength=810,foreground=MUTED).pack(anchor='w')
        self.canvas.bind('<Configure>',lambda _:self.draw());self.canvas.bind('<Button-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        try:self.devices=load_layout()['devices']
        except (OSError,ValueError) as exc:messagebox.showerror('RGB layout',f'Could not load layout: {exc}\nStored file was not changed.',parent=root)
        self.refresh_choices();self.select(0 if self.devices else None);self.poll()

    def bounds(self):
        return 20,76,max(self.canvas.winfo_width(),330)-15,max(self.canvas.winfo_height(),360)-18

    def group_geometry(self,d):
        x0,y0,x1,y1=self.bounds()
        if d['kind']=='Fan':
            return fan_geometry(d.get('fan_count',1),d['orientation'],x1-x0-24,y1-y0-100)
        return [],27,104,72

    def screen(self,d):
        x0,y0,x1,y1=self.bounds()
        _,_,w,h=self.group_geometry(d)
        mx,my=w/2+10,h/2+32
        return x0+mx+d['x']*(x1-x0-2*mx),y0+my+d['y']*(y1-y0-2*my)

    def position(self,x,y,d=None):
        x0,y0,x1,y1=self.bounds()
        if d is None: w,h=104,72
        else: _,_,w,h=self.group_geometry(d)
        mx,my=w/2+10,h/2+32
        return max(0,min(1,(x-x0-mx)/max(1,x1-x0-2*mx))),max(0,min(1,(y-y0-my)/max(1,y1-y0-2*my)))

    def show_fan_count(self):
        if self.selected is not None and self.kind.get()=='Fan':
            self.count_row.pack(fill='x',pady=3,after=self.orientation_box)
        else:
            self.count_row.pack_forget()

    def draw_fan(self,x,y,r,color):
        c=self.canvas
        c.create_rectangle(x-r,y-r,x+r,y+r,fill=PANEL,outline=color,width=2)
        c.create_oval(x-r*.81,y-r*.81,x+r*.81,y+r*.81,outline=color,width=2)
        for angle in range(0,360,90):
            a=math.radians(angle);bx,by=x+r*.41*math.cos(a),y+r*.41*math.sin(a)
            c.create_oval(bx-r*.22,by-r*.22,bx+r*.22,by+r*.22,fill=color,outline='')
        c.create_oval(x-r*.18,y-r*.18,x+r*.18,y+r*.18,fill=TEXT,outline='')

    def icon(self,x,y,d,selected=False):
        c=self.canvas;color=d['color'];vertical=d['orientation']=='Vertical'
        offsets,r,w,h=self.group_geometry(d)
        if selected:c.create_rectangle(x-w/2-5,y-h/2-5,x+w/2+5,y+h/2+25,outline=ACCENT,dash=(3,3))
        if d['kind']=='Fan':
            for dx,dy in offsets:self.draw_fan(x+dx,y+dy,r,color)
        elif d['kind']=='LED strip':
            if vertical:c.create_rectangle(x-7,y-32,x+7,y+32,fill=PANEL,outline='#65718d')
            else:c.create_rectangle(x-43,y-7,x+43,y+7,fill=PANEL,outline='#65718d')
            for i in range(9):
                dx,dy=(0,-28+i*7) if vertical else (-36+i*9,0)
                c.create_rectangle(x+dx-3,y+dy-3,x+dx+3,y+dy+3,fill=color,outline='')
        else:
            for i in range(6):
                o=(i-2.5)*7
                coords=(x+o,y-30,x+o+8,y-5,x+o-8,y+10,x+o,y+30) if vertical else (x-46,y+o,x-15,y+o-7,x+15,y+o+7,x+46,y+o)
                c.create_line(*coords,fill=color,width=4,smooth=True)
            if vertical:
                c.create_rectangle(x-25,y-36,x+25,y-29,fill='#53617c',outline='')
                c.create_rectangle(x-25,y+29,x+25,y+36,fill='#53617c',outline='')
            else:
                c.create_rectangle(x-51,y-25,x-44,y+25,fill='#53617c',outline='')
                c.create_rectangle(x+44,y-25,x+51,y+25,fill='#53617c',outline='')
        label=d['name'] if len(d['name'])<=16 else d['name'][:15]+'…'
        count_label=f' · {d.get("fan_count",1)} fans' if d['kind']=='Fan' and d.get('fan_count',1)>1 else ''
        c.create_text(x,y+h/2+14,text=f'{label}{count_label} · P{d["port"]}',fill=TEXT,font=('Sans',9,'bold'))

    def draw(self):
        c=self.canvas;c.delete('all');x0,y0,x1,y1=self.bounds()
        width=(x1-x0)/3
        for i,label in enumerate(('+ FAN','+ LED STRIP','+ ARGB CABLE')):
            left=x0+i*width
            c.create_rectangle(left,10,left+width-5,51,fill=PANEL,outline=ACCENT)
            c.create_text(left+(width-5)/2,30,text=label,fill=ACCENT,font=('Sans',9,'bold'))
        c.create_rectangle(x0,y0,x1,y1,fill='#191f2c',outline='#65718d',width=3)
        c.create_text(x0+12,y0+17,text='PC CASE · SIDE VIEW',fill=MUTED,anchor='w',font=('Sans',9,'bold'))
        mw=x1-x0;cy=y0+(y1-y0)*.4
        c.create_rectangle(x0+mw*.18,y0+58,x0+mw*.7,y1-95,outline='#303c54',width=2)
        c.create_rectangle(x0+mw*.33,cy-22,x0+mw*.5,cy+22,outline='#35425c',width=2)
        c.create_text(x0+mw*.415,cy,text='CPU',fill='#53617c')
        c.create_rectangle(x0+mw*.2,cy+53,x0+mw*.72,cy+80,outline='#35425c',width=2)
        c.create_text(x0+mw*.46,cy+66,text='GPU',fill='#53617c')
        c.create_rectangle(x0+12,y1-65,x1-12,y1-12,outline='#303c54');c.create_text(x0+25,y1-38,text='PSU',fill='#53617c',anchor='w')
        c.create_text(x1-13,(y0+y1)/2,text='FRONT',fill='#53617c',angle=90)
        for i,d in enumerate(self.devices):self.icon(*self.screen(d),d,i==self.selected)
        if not self.devices:c.create_text((x0+x1)/2,cy+110,text='Drag a device from above\nor use Add device',fill=MUTED,justify='center')
        if isinstance(self.dragging,str):
            self.icon(*self.ghost,dict(kind=self.dragging,name='NEW DEVICE',port='?',orientation='Horizontal',color=ACCENT),True)

    def refresh_choices(self):self.choices.configure(values=[f'{d["name"]} · port {d["port"]}' for d in self.devices])

    def select(self,index):
        self.selected=index;valid=index is not None and 0<=index<len(self.devices)
        for widget in (self.name_entry,self.color_entry,self.brightness_box,self.speed_box,self.color_button,self.update_button,self.remove_button):widget.configure(state='normal' if valid else 'disabled')
        for widget in (self.port_box,self.kind_box,self.orientation_box,self.effect_box):widget.configure(state='readonly' if valid else 'disabled')
        if valid:
            d=self.devices[index];self.choices.current(index)
            for key in ('name','kind','orientation','color','effect','brightness','speed'):getattr(self,key).set(d[key])
            self.fan_count.set(d.get('fan_count',1))
            self.port.set(str(d['port']))
        else:self.choice.set('');self.name.set('');self.port.set('')
        self.show_fan_count()
        self.draw()

    def select_choice(self,_=None):self.select(self.choices.current() if self.devices else None)

    def mark_dirty(self):self.dirty=True;self.status.set('Layout edited · Save layout to keep it; Apply layout RGB to send colors.')

    def add(self,kind,x=.78,y=.35):
        try:self.devices.append(placement(self.devices,kind,x,y))
        except ValueError as exc:self.status.set(str(exc));return
        self.refresh_choices();self.select(len(self.devices)-1);self.mark_dirty()

    def update_selected(self):
        if self.selected is None:return True
        try:
            devices=[dict(d) for d in self.devices]
            values={key:getattr(self,key).get() for key in ('name','kind','orientation','color','effect','brightness','speed')}
            values['fan_count']=self.fan_count.get()
            values['port']=int(self.port.get());devices[self.selected].update(values)
            self.devices=validate_layout(dict(version=1,devices=devices))['devices']
        except (ValueError,tk.TclError) as exc:
            messagebox.showerror('RGB device',str(exc),parent=self.root);return False
        self.refresh_choices();self.select(self.selected);self.mark_dirty();return True

    def choose_color(self):
        current=self.color.get()
        try:self.canvas.winfo_rgb(current)
        except tk.TclError:current=ACCENT
        _,color=colorchooser.askcolor(color=current,parent=self.root,title='Device RGB color')
        if color:self.color.set(color)

    def remove(self):
        if self.selected is None:return
        del self.devices[self.selected];self.refresh_choices();self.select(0 if self.devices else None);self.mark_dirty()

    def press(self,e):
        x0,_,x1,_=self.bounds()
        if x0<=e.x<=x1 and 10<=e.y<=51:
            i=min(2,int((e.x-x0)/((x1-x0)/3)));self.dragging=KINDS[i];self.ghost=(e.x,e.y);return
        for i in reversed(range(len(self.devices))):
            x,y=self.screen(self.devices[i])
            _,_,w,h=self.group_geometry(self.devices[i])
            if abs(x-e.x)<=w/2+5 and abs(y-e.y)<=h/2+25:
                self.select(i);self.dragging=i;self.offset=(e.x-x,e.y-y);return
        self.select(None)

    def motion(self,e):
        if isinstance(self.dragging,str):self.ghost=(e.x,e.y)
        elif self.dragging is not None:
            x,y=self.position(e.x-self.offset[0],e.y-self.offset[1],self.devices[self.dragging]);self.devices[self.dragging].update(x=x,y=y);self.mark_dirty()
        else:return
        self.draw()

    def release(self,e):
        if isinstance(self.dragging,str):
            x0,y0,x1,y1=self.bounds()
            if x0<=e.x<=x1 and y0<=e.y<=y1:self.add(self.dragging,*self.position(e.x,e.y))
        self.dragging=None;self.draw()

    def save(self):
        if not self.update_selected():return
        try:save_layout(dict(version=1,devices=self.devices));self.dirty=False;self.status.set('RGB layout saved. Loading it does not apply colors automatically.')
        except (OSError,ValueError) as exc:messagebox.showerror('Save RGB layout',str(exc),parent=self.root)

    def apply(self):
        if not self.update_selected():return
        try:
            settings=scene_settings(dict(version=1,devices=self.devices))
            self.player.start(settings)
            self.status.set('Applying RGB layout. Unassigned ports turn dark. Save layout to keep these settings.')
        except ValueError as exc:messagebox.showerror('Apply RGB layout',str(exc),parent=self.root)

    def stop(self):self.player.stop();self.status.set('Stopping RGB animation; last frame stays lit.')

    def poll(self):
        counts=self.player.port_counts
        if counts:self.topology.set('Detected LEDs · '+ ' · '.join(f'P{i}: {n}' for i,n in enumerate(counts,1)))
        else:self.topology.set('LED counts are read from the hub when RGB starts.')
        self.root.after(1000,self.poll)
