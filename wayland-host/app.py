#!/usr/bin/env python3
"""DeskDock Python: a native desktop launcher for Wayland input sharing."""
import argparse
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
gi.require_version('Graphene','1.0')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Graphene

from services import APP_ID, DeviceWatcher, Worker, load_settings, save_settings, send_file
from branding import NAME, ICON_NAME, ICON_PATH

EDGES = ['right','left','bottom','top']

class App(Adw.Application):
    def __init__(self,smoke=False,screenshot=None):
        super().__init__(application_id=APP_ID,flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        Gtk.Window.set_default_icon_name(ICON_NAME)
        self.smoke=smoke
        self.screenshot=screenshot
        self.window=None
        self.settings=load_settings()
        self.devices=[]
        self.busy=False
        self.closing=False
        self.last_error=''
        self.phone_clipboard=None
        self.desktop_clipboard=None
        self.clipboard_generation=0
        self.requested_serial=None
        self.tray=None
        self.tray_ready=False
        self.worker=Worker(GLib.idle_add,self.event)
        self.watcher=DeviceWatcher(GLib.idle_add,self.devices_changed)
        self.connect('activate',self.on_activate)
        self.connect('shutdown',self.shutdown)
        # Keep the application and its worker alive when every window is hidden.
        # Only the explicit Quit action ends the application.
        self.hold()
        action=Gio.SimpleAction.new('quit',None)
        action.connect('activate',lambda *_:self.close())
        self.add_action(action)
        for name,callback in (('show',self.on_activate),('start',self.start_clicked),('stop',self.stop_clicked),('hide',self.hide_window)):
            action=Gio.SimpleAction.new(name,None)
            action.connect('activate',lambda *_,fn=callback:fn())
            self.add_action(action)
        self.sharing_action=Gio.SimpleAction.new_stateful('sharing',None,GLib.Variant('b',False))
        self.add_action(self.sharing_action)
        self.lookup_action('start').set_enabled(False)
        self.lookup_action('stop').set_enabled(False)
        connect_action=Gio.SimpleAction.new('connect',GLib.VariantType.new('s'))
        connect_action.connect('activate',self.request_connection)
        self.add_action(connect_action)
        self.set_accels_for_action('app.quit',['<Primary>q'])

    def request_connection(self,action,parameter):
        self.requested_serial=parameter.get_string()
        self.on_activate()
        self.start_requested()

    def start_requested(self):
        if not self.requested_serial or not self.window or not getattr(self,'supported',False):return False
        if self.worker.process:
            self.requested_serial=None
            self.toast('A sharing session is already running.')
            return False
        if self.requested_serial.startswith('wifi://'):
            self.wifi.set_active(True);self.address.set_text(self.requested_serial.removeprefix('wifi://'));self.requested_serial=None;self.start_clicked();return False
        for index,device in enumerate(self.devices):
            if device.serial==self.requested_serial and device.state=='device':
                self.requested_serial=None
                self.device.set_selected(index)
                self.start_clicked()
                return False
        return False

    def on_activate(self,*_):
        if self.window:
            self.window.present()
            return
        self.window=Adw.ApplicationWindow(application=self,title=NAME,default_width=570,default_height=780)
        self.window.connect('close-request',lambda *_:self.window_closed())
        self.overlay=Adw.ToastOverlay()
        root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header=Adw.HeaderBar()
        self.hide_button=Gtk.Button(icon_name='window-minimize-symbolic',tooltip_text='Hide to tray',sensitive=False)
        self.hide_button.connect('clicked',lambda *_:self.hide_window())
        header.pack_start(self.hide_button)
        menu=Gio.Menu();menu.append('Quit '+NAME,'app.quit')
        header.pack_end(Gtk.MenuButton(icon_name='open-menu-symbolic',menu_model=menu))
        root.append(header)
        scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=22,margin_top=24,margin_bottom=24,margin_start=28,margin_end=28)
        clamp=Adw.Clamp(maximum_size=650);clamp.set_child(content);scroll.set_child(clamp);root.append(scroll)
        self.overlay.set_child(root);self.window.set_content(self.overlay)
        hero=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        icon=Gtk.Image.new_from_file(str(ICON_PATH));icon.set_pixel_size(64);hero.append(icon)
        title=Gtk.Label(label='One mouse. Two screens.');title.add_css_class('title-1');hero.append(title)
        self.status=Gtk.Label(label='Checking your desktop…',wrap=True,justify=Gtk.Justification.CENTER)
        hero.append(self.status);content.append(hero)
        self.spinner=Gtk.Spinner();hero.append(self.spinner)
        group=Adw.PreferencesGroup(title='Connection')
        self.device_model=Gtk.StringList.new(['Looking for Android devices…'])
        self.device=Gtk.DropDown(model=self.device_model,hexpand=True)
        row=Adw.ActionRow(title='Phone');row.add_suffix(self.device);row.set_activatable_widget(self.device);group.add(row)
        edge_row=Adw.ActionRow(title='Phone position',subtitle='Which desktop edge leads to your phone?')
        self.edge=Gtk.DropDown.new_from_strings(['Right','Left','Below','Above']);self.edge.set_selected(EDGES.index(self.settings['edge']))
        edge_row.add_suffix(self.edge);group.add(edge_row)
        speed_row=Adw.ActionRow(title='Pointer speed')
        self.speed=Gtk.SpinButton.new_with_range(.1,4,.1);self.speed.set_digits(1);self.speed.set_value(self.settings['speed']);speed_row.add_suffix(self.speed);group.add(speed_row)
        self.repeat=Adw.SwitchRow(title='Repeat held keys');self.repeat.set_active(self.settings['repeat']);group.add(self.repeat)
        self.pairing=Adw.PasswordEntryRow(title='Wi-Fi pairing code (not needed for ADB)')
        self.pairing.set_text(self.settings.get('pairing_code',''));group.add(self.pairing)
        self.wifi=Adw.SwitchRow(title='Use direct Wi-Fi instead of ADB');self.wifi.set_active(self.settings['serial'].startswith('wifi://'));group.add(self.wifi)
        self.address=Adw.EntryRow(title='Wi-Fi address and port');self.address.set_text(self.settings.get('wifi_address',''));group.add(self.address)
        self.fingerprint=Adw.EntryRow(title='Phone TLS SHA-256 fingerprint');self.fingerprint.set_text(self.settings.get('tls_fingerprint',''));group.add(self.fingerprint)
        self.wifi.connect('notify::active',lambda *_:self.controls());self.address.connect('changed',lambda *_:self.controls())
        content.append(group)
        from layout_gtk import LayoutEditor
        self.placement=LayoutEditor(self.settings,self.layout_changed);content.append(self.placement)
        self.edge.connect('notify::selected',lambda *_:self.placement.set_edge(EDGES[self.edge.get_selected()]) if self.placement.model.edge!=EDGES[self.edge.get_selected()] else None)
        tools=Adw.PreferencesGroup(title='Phone tools')
        self.clip_sync=Adw.SwitchRow(title='Share clipboard',subtitle='Sync text automatically when you enter the phone');tools.add(self.clip_sync)
        self.clip_sync.set_active(self.settings['share_clipboard'])
        self.window.get_display().get_clipboard().connect('changed',self.clipboard_changed)
        self.clip_sync.connect('notify::active',self.clipboard_toggled)
        self.copy_clip=self.tool(tools,'Phone clipboard','Copy the last text received from your phone','Copy',self.copy_phone_clipboard)
        self.paste=self.tool(tools,'Paste text','Type text into the focused field on your phone','Paste…',self.paste_clicked)
        self.send_file=self.tool(tools,'Send a file','Save a file in your phone’s Downloads folder','Choose…',self.file_clicked)
        content.append(tools)
        actions=Gtk.Box(spacing=10,homogeneous=True)
        self.start=Gtk.Button(label='Start sharing');self.start.add_css_class('suggested-action');self.start.connect('clicked',self.start_clicked);actions.append(self.start)
        self.stop=Gtk.Button(label='Stop sharing',sensitive=False);self.stop.connect('clicked',self.stop_clicked);actions.append(self.stop);content.append(actions)
        help_label=Gtk.Label(label='Move past the chosen edge to control your phone.\nMove back to return, or press Ctrl + Alt + Shift + Esc.',wrap=True,justify=Gtk.Justification.CENTER)
        help_label.add_css_class('dim-label');content.append(help_label)
        setup=Gtk.Expander(label='First-time setup')
        instructions=Gtk.Label(label='1. Install the new desk dockt APK on your phone.\n2. Enable USB debugging and approve this computer.\n3. Enable desk dockt input control and tap Start sharing.\n4. Select your phone here and start sharing. Approve GNOME’s input-capture dialog when it appears.',wrap=True,xalign=0,margin_top=12)
        setup.set_child(instructions);content.append(setup)
        diagnostics=Gtk.Expander(label='Connection details')
        self.log=Gtk.TextView(editable=False,cursor_visible=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR)
        log_scroll=Gtk.ScrolledWindow(min_content_height=110,max_content_height=170);log_scroll.set_child(self.log);diagnostics.set_child(log_scroll);content.append(diagnostics)
        self.device.connect('notify::selected',lambda *_:self.controls())
        self.controls();self.window.present()
        self.background(self.check_support,self.checked)
        self.watcher.start()
        if not self.smoke:self.start_tray()
        if self.smoke: GLib.timeout_add_seconds(2,self.smoke_finish)

    def tool(self,group,title,subtitle,label,callback):
        row=Adw.ActionRow(title=title,subtitle=subtitle)
        button=Gtk.Button(label=label,valign=Gtk.Align.CENTER);button.connect('clicked',callback)
        row.add_suffix(button);group.add(row)
        return button

    def toast(self,message):
        self.overlay.add_toast(Adw.Toast.new(message))

    def background(self,work,done):
        def run():
            try: result=work();error=None
            except Exception as exc: result=None;error=str(exc)
            GLib.idle_add(done,result,error)
        threading.Thread(target=run,daemon=True).start()

    def check_support(self):
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('host.py')),'--check'],capture_output=True,text=True,timeout=20)
        if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def checked(self,result,error):
        self.supported=not error
        self.status.set_label('Wayland input sharing is ready.' if not error else 'Desktop input sharing is unavailable.')
        self.append_log(result or error)
        if error:self.toast(error)
        self.controls()
        self.start_requested()
        return False

    def selected(self):
        index=self.device.get_selected()
        return self.devices[index] if index<len(self.devices) else None

    def devices_changed(self,devices,error=None):
        previous=self.selected()
        serial=previous.serial if previous else self.settings['serial']
        self.devices=devices
        self.device_model.splice(0,self.device_model.get_n_items(),[d.label for d in devices] or ['No Android devices connected'])
        self.device.set_selected(next((i for i,d in enumerate(devices) if d.serial==serial),0))
        if error:self.append_log(error)
        self.controls()
        self.start_requested()
        return False

    def controls(self):
        if not self.window:return
        selected=self.selected();ready=bool(self.address.get_text().strip()) if self.wifi.get_active() else bool(selected and selected.state=='device')
        running=self.worker.process is not None
        self.start.set_sensitive(ready and not running and not self.busy and getattr(self,'supported',False))
        self.stop.set_sensitive(running and not self.worker.stopping)
        self.lookup_action('start').set_enabled(self.start.get_sensitive())
        self.lookup_action('stop').set_enabled(self.stop.get_sensitive())
        self.sharing_action.set_state(GLib.Variant('b',running))
        for control in (self.placement,self.device,self.edge,self.speed,self.repeat,self.pairing,self.wifi,self.address,self.fingerprint):control.set_sensitive(not running and not self.busy)
        for control in (self.paste,):control.set_sensitive(running and getattr(self,'connected',False) and not self.worker.stopping)
        self.copy_clip.set_sensitive(self.phone_clipboard is not None)
        self.send_file.set_sensitive(ready and not self.wifi.get_active() and not self.busy)
        if not running and selected and selected.state=='unauthorized':
            self.status.set_label('Unlock your phone and approve USB debugging for this computer.')

    def start_clicked(self,*_):
        selected=self.selected()
        if self.wifi.get_active():serial='wifi://'+self.address.get_text().strip().removeprefix('wifi://')
        else:
            if not selected or selected.state!='device':return
            serial=selected.serial
        self.settings.update(serial=serial,edge=EDGES[self.edge.get_selected()],speed=self.speed.get_value(),repeat=self.repeat.get_active())
        self.settings['pairing_code']=self.pairing.get_text().strip()
        self.settings['wifi_address']=self.address.get_text().strip();self.settings['tls_fingerprint']=self.fingerprint.get_text().strip()
        try:
            save_settings(self.settings)
            self.last_error='';self.connected=False
            self.worker.start(serial,self.settings['edge'],self.settings['speed'],self.settings['repeat'])
            self.status.set_label('Connecting to your phone…');self.spinner.start()
        except Exception as exc:self.toast(str(exc))
        self.controls()

    def stop_clicked(self,*_):
        self.worker.stop();self.status.set_label('Stopping input sharing…');self.controls()

    def append_log(self,message):
        if not message:return
        buffer=self.log.get_buffer()
        buffer.insert(buffer.get_end_iter(),message+'\n')
        if buffer.get_line_count()>120:
            start=buffer.get_start_iter();end=buffer.get_iter_at_line(20)
            if isinstance(end,tuple):end=end[-1]
            buffer.delete(start,end)

    def event(self,event):
        kind=event['type']
        if kind=='permission':self.status.set_label('Approve the GNOME input-capture dialog to continue.')
        elif kind=='ready':
            self.connected=True;self.spinner.stop()
            self.worker.send('clipboard-sharing',enabled=self.clip_sync.get_active())
            self.status.set_label('Sharing is ready. Move past the '+self.settings['edge']+' edge.')
            self.clipboard_changed(self.window.get_display().get_clipboard(),force=True)
        elif kind=='active':
            self.status.set_label('Your mouse and keyboard are controlling the phone.')
            if self.clip_sync.get_active() and self.desktop_clipboard is not None:
                if self.worker.send('clipboard',text=self.desktop_clipboard):self.phone_clipboard=self.desktop_clipboard
            self.clipboard_changed(self.window.get_display().get_clipboard(),force=True)
        elif kind=='clipboard':
            self.clipboard_generation+=1
            if event['text']!=self.phone_clipboard:
                self.phone_clipboard=event['text']
                if self.clip_sync.get_active():self.window.get_display().get_clipboard().set(self.phone_clipboard)
        elif kind=='error':
            self.last_error=event['message'];self.append_log(self.last_error)
        elif kind=='log':self.append_log(event['message'])
        elif kind=='exited':
            self.connected=False;self.spinner.stop()
            if self.closing:self.quit();return False
            if event['stopped']:self.status.set_label('Sharing stopped. Your desktop has control.')
            else:
                message=self.last_error or 'The connection ended. Check the phone and try again.'
                self.status.set_label('Connection ended. Check Connection details.');self.toast(message)
        self.controls();return False

    def layout_changed(self,edge,layout):
        self.settings.update(edge=edge,phone_layout=layout);save_settings(self.settings)
        if self.edge.get_selected()!=EDGES.index(edge):self.edge.set_selected(EDGES.index(edge))

    def clipboard_toggled(self,*_):
        self.settings['share_clipboard']=self.clip_sync.get_active()
        if not self.settings['share_clipboard']:self.desktop_clipboard=None
        save_settings(self.settings)
        self.worker.send('clipboard-sharing',enabled=self.clip_sync.get_active())
        self.clipboard_changed(self.window.get_display().get_clipboard(),force=True)

    def clipboard_changed(self,clipboard,force=False):
        self.clipboard_generation+=1
        generation=self.clipboard_generation
        if not self.clip_sync.get_active():return
        def received(clipboard,result):
            try:
                text=clipboard.read_text_finish(result)
                if generation!=self.clipboard_generation or not self.clip_sync.get_active():return
                if text is not None:self.desktop_clipboard=text
                if (getattr(self,'connected',False) and text is not None
                        and (force or text!=self.phone_clipboard)):
                    if self.worker.send('clipboard',text=text):self.phone_clipboard=text
            except GLib.Error:pass
        clipboard.read_text_async(None,received)

    def copy_phone_clipboard(self,*_):
        if self.phone_clipboard is not None:
            self.window.get_display().get_clipboard().set(self.phone_clipboard)
            self.toast('Phone text copied to your desktop clipboard.')

    def paste_clicked(self,*_):
        dialog=Adw.Window(transient_for=self.window,modal=True,title='Paste text',default_width=440,default_height=300)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_top=20,margin_bottom=20,margin_start=20,margin_end=20)
        box.append(Gtk.Label(label='Text will be typed into the focused phone field.',wrap=True))
        entry=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(entry);box.append(scroll)
        button=Gtk.Button(label='Send to phone');button.add_css_class('suggested-action')
        def send(*_):
            buffer=entry.get_buffer();text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
            if self.worker.send('text',text=text):self.toast('Text sent to your phone.')
            else:self.toast('Start input sharing before sending text.')
            dialog.close()
        button.connect('clicked',send);box.append(button);dialog.set_content(box);dialog.present()

    def file_clicked(self,*_):
        selected=self.selected()
        if not selected:return
        chooser=Gtk.FileDialog(title='Send a file to phone')
        def chosen(chooser,result):
            try:
                file=chooser.open_finish(result)
                path=file.get_path()
                if not path:raise ValueError('Choose a local file.')
            except (GLib.Error,ValueError):return
            self.busy=True;self.controls();self.toast('Sending '+Path(path).name+'…')
            def work():
                return send_file(selected.serial,path)
            def done(result,error):
                self.busy=False;self.controls();self.append_log(result or error)
                self.toast('Saved in Downloads as '+Path(result).name if not error else 'File transfer failed. See Connection details.')
                return False
            self.background(work,done)
        chooser.open(self.window,None,chosen)

    def close(self):
        if self.busy:
            self.toast('Wait for the file transfer to finish before closing.');return True
        if self.worker.process:
            self.closing=True;self.stop_clicked();return True
        self.quit();return True

    def start_tray(self):
        self.tray=subprocess.Popen([sys.executable,str(Path(__file__).with_name('tray.py'))],
                                   stdout=subprocess.PIPE,text=True)
        process=self.tray
        def monitor():
            for line in process.stdout:
                if line.strip()=='READY':GLib.idle_add(self.tray_changed,process,True)
            process.wait();process.stdout.close()
            GLib.idle_add(self.tray_changed,process,False)
        threading.Thread(target=monitor,daemon=True).start()

    def tray_changed(self,process,ready):
        if process is not self.tray:return False
        self.tray_ready=ready
        self.hide_button.set_sensitive(ready)
        if not ready and not self.closing:self.window.present()
        return False

    def hide_window(self):
        if self.tray_ready:self.window.set_visible(False)
        else:self.window.minimize()

    def window_closed(self):
        self.hide_window()
        return True

    def shutdown(self,*_):
        self.watcher.close();self.worker.stop()
        if self.tray and self.tray.poll() is None:
            self.tray.terminate()
            self.tray.wait(timeout=3)

    def smoke_finish(self):
        assert self.window.get_visible()
        assert self.start.get_label()=='Start sharing'
        if self.screenshot:
            paintable=Gtk.WidgetPaintable.new(self.window)
            snapshot=Gtk.Snapshot()
            w,h=self.window.get_width(),self.window.get_height()
            paintable.snapshot(snapshot,w,h)
            node=snapshot.to_node()
            if node:
                texture=self.window.get_renderer().render_texture(node,Graphene.Rect().init(0,0,w,h))
                texture.save_to_png(self.screenshot)
        print('GUI smoke test: window and controls created successfully.',flush=True)
        self.quit();return False

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--screenshot',help=argparse.SUPPRESS)
    parser.add_argument('--connect',metavar='SERIAL',help='Start sharing with this connected ADB device')
    args=parser.parse_args()
    application=App(smoke=args.smoke_test,screenshot=args.screenshot)
    application.register(None)
    if application.get_is_remote():
        application.activate()
        if args.connect:application.activate_action('connect',GLib.Variant('s',args.connect))
        sys.exit(0)
    application.requested_serial=args.connect
    sys.exit(application.run([sys.argv[0]]))
