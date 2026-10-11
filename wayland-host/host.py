#!/usr/bin/env python3
"""GNOME Wayland edge switching for the repaired DeskDock Android app."""
import argparse
import json
import threading
import signal
import sys
import uuid

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from eis import Receiver
from protocol import Phone
from cursor import Cursor

SERVICE = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'
INTERFACE = 'org.freedesktop.portal.InputCapture'
from keymap import KEYS


def barrier(zones, edge):
    """Choose a full monitor edge at the extreme boundary of the monitor union."""
    if not zones:
        raise ValueError('The portal returned no monitors')
    extrema = {'right': lambda z:z[2]+z[0], 'left': lambda z:-z[2],
               'bottom': lambda z:z[3]+z[1], 'top': lambda z:-z[3]}
    w,h,x,y = max(zones, key=extrema[edge])
    lines = {'right':(x+w,y,x+w,y+h-1), 'left':(x,y,x,y+h-1),
             'bottom':(x,y+h,x+w-1,y+h), 'top':(x,y,x+w-1,y)}
    return (w,h,x,y), lines[edge]

class Portal:
    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        self.object = self.bus.get_object(SERVICE, PATH)
        self.api = dbus.Interface(self.object, INTERFACE)
        props = dbus.Interface(self.object, 'org.freedesktop.DBus.Properties')
        self.version = int(props.Get(INTERFACE, 'version'))
        self.capabilities = int(props.Get(INTERFACE, 'SupportedCapabilities'))
        self.session = None
        self.pending = None
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        if self.pending:
            request,loop = self.pending
            try:
                dbus.Interface(self.bus.get_object(SERVICE,request), "org.freedesktop.portal.Request").Close()
            except dbus.DBusException:
                pass
            loop.quit()

    def request(self, method, *args, options=None, options_index=None):
        if self.cancelled:
            raise RuntimeError('Connection stopped')
        token = 'deskdock_' + uuid.uuid4().hex
        owner = self.bus.get_unique_name()[1:].replace('.', '_')
        path = PATH + '/request/' + owner + '/' + token
        loop = GLib.MainLoop()
        result = []
        def response(code, data):
            result.append((int(code), data))
            loop.quit()
        subscription = self.bus.add_signal_receiver(response, signal_name='Response',
            dbus_interface='org.freedesktop.portal.Request', path=path, bus_name=SERVICE)
        opts = dict(options or {})
        opts['handle_token'] = token
        returned = None
        timeout = None
        try:
            arguments = list(args)
            arguments.insert(len(arguments) if options_index is None else options_index, dbus.Dictionary(opts, signature='sv'))
            returned = getattr(self.api, method)(*arguments)
            if str(returned) != path:
                raise RuntimeError('Portal returned an unexpected request path')
            self.pending = (returned,loop)
            timeout = GLib.timeout_add_seconds(120, lambda: (loop.quit(), False)[1])
            if not result:
                loop.run()
            if not result:
                raise TimeoutError('Portal permission request timed out')
            code, data = result[0]
            if code:
                raise RuntimeError(f'Portal request {method} declined or failed ({code})')
            return data
        finally:
            self.pending = None
            subscription.remove()
            if timeout and GLib.MainContext.default().find_source_by_id(timeout):
                GLib.source_remove(timeout)
            if not result and returned:
                dbus.Interface(self.bus.get_object(SERVICE, returned), 'org.freedesktop.portal.Request').Close()

    def start(self):
        opts = {'session_handle_token':'deskdock_' + uuid.uuid4().hex}
        if self.version >= 2:
            result = self.api.CreateSession2(dbus.Dictionary(opts, signature='sv'))
            self.session = result['session_handle']
            result = self.request('Start', self.session, '', options={'capabilities':dbus.UInt32(3)})
        else:
            opts['capabilities'] = dbus.UInt32(3)
            result = self.request('CreateSession', '', options=opts)
            self.session = result['session_handle']
        if int(result.get('capabilities',0)) & 3 != 3:
            raise RuntimeError('Portal did not grant both keyboard and pointer capture')

    def close(self):
        if self.session:
            try:
                dbus.Interface(self.bus.get_object(SERVICE, self.session), 'org.freedesktop.portal.Session').Close()
            except dbus.DBusException:
                pass
            self.session = None

class Host:
    def __init__(self, phone, portal, edge, speed, notify=None, repeat=True):
        self.phone, self.portal, self.edge, self.speed = phone, portal, edge, speed
        self.notify = notify or (lambda **event: None)
        self.repeat = repeat
        self.repeat_source = None
        self.repeat_key = None
        self.stopping = False
        self.temporary_entry = False
        self.active = None
        self.x = self.y = 0
        self.zone = None
        self.keys = {}
        self.buttons = set()
        self.physical_keys = set()
        self.loop = GLib.MainLoop()
        self.receiver = None
        self.cursor = None
        self.matches = []
        self.sources = []
        self.failure = None
        self.scroll_x = self.scroll_y = 0
        phone.on_disconnect = lambda: GLib.idle_add(self.failed, str(phone.error))

    def failed(self, message):
        self.failure = message
        self.notify(type="error",message=message)
        print('Stopping: ' + message, file=sys.stderr, flush=True)
        self.loop.quit()
        return False

    def zones(self):
        if self.active is not None:
            self.release()
        p = self.portal
        result = p.request('GetZones', p.session)
        self.zone, line = barrier([tuple(map(int,z)) for z in result['zones']], self.edge)
        definition = dbus.Dictionary({'barrier_id':dbus.UInt32(1),
                                      'position':dbus.Struct(line, signature='iiii')}, signature='sv')
        result = p.request('SetPointerBarriers', p.session,
            dbus.Array([definition], signature='a{sv}'), dbus.UInt32(result['zone_set']),
            options_index=1)
        if result.get('failed_barriers'):
            raise RuntimeError('Compositor rejected the pointer barrier')
        p.api.Enable(p.session, dbus.Dictionary({}, signature='sv'))
        self.notify(type='ready',edge=self.edge,width=self.phone.width,height=self.phone.height)
        print(f'Ready: cross the {self.edge} edge of monitor {self.zone}. Ctrl+Alt+Shift+Esc returns to desktop.', flush=True)

    def signal(self, name, session, options):
        if session != self.portal.session:
            return
        try:
            if name == 'Activated':
                self.temporary_entry = False
                self.active = int(options['activation_id'])
                if self.cursor:self.cursor.set(True)
                w,h,x,y = self.zone
                cx,cy = map(float, options.get('cursor_position',(x,y)))
                if self.edge in ('right','left'):
                    self.x = 2 if self.edge == 'right' else self.phone.width-3
                    self.y = max(0,min(self.phone.height-1,(cy-y)/h*self.phone.height))
                else:
                    self.x = max(0,min(self.phone.width-1,(cx-x)/w*self.phone.width))
                    self.y = 2 if self.edge == 'bottom' else self.phone.height-3
                self.phone.enter(True)
                self.phone.move(self.x,self.y)
                self.notify(type="active")
            elif name == 'Deactivated':
                if int(options.get('activation_id', -1)) == self.active:
                    self.clear()
            elif name == 'Disabled':
                self.clear()
                self.failed('Compositor disabled capture. Run host again to re-enable.')
            elif name == 'ZonesChanged':
                GLib.idle_add(self.refresh)
        except Exception as exc:
            self.failed(str(exc))

    def refresh(self):
        try:
            self.zones()
        except Exception as exc:
            self.failed(str(exc))
        return False

    def clear(self):
        entered = self.active is not None or self.temporary_entry
        self.temporary_entry = False
        self.active = None
        if self.cursor:self.cursor.set(False)
        try:
            for key,(code,char) in self.keys.items():
                self.phone.key(code,char,False)
            for button in self.buttons:
                self.phone.button(button,False,self.x,self.y)
            if entered:
                self.phone.enter(False)
        finally:
            self.cancel_repeat()
            self.keys.clear()
            self.buttons.clear()
            self.physical_keys.clear()
            self.scroll_x = self.scroll_y = 0
            if entered: self.notify(type="ready",edge=self.edge,width=self.phone.width,height=self.phone.height)

    def release(self):
        activation = self.active
        if activation is None:
            return
        # Release desktop capture even if the phone socket has already failed.
        try:
            w,h,x,y = self.zone
            if self.edge in ('right','left'):
                cursor = (x+w-2 if self.edge == 'right' else x+1, y+self.y/self.phone.height*(h-1))
            else:
                cursor = (x+self.x/self.phone.width*(w-1), y+h-2 if self.edge == 'bottom' else y+1)
            self.portal.api.Release(self.portal.session, dbus.Dictionary({
                'activation_id':dbus.UInt32(activation),
                'cursor_position':dbus.Struct(tuple(dbus.Double(value) for value in cursor),signature='dd')}, signature='sv'))
        finally:
            self.clear()

    def stop(self):
        self.stopping = True
        self.portal.cancel()
        self.loop.quit()
        return False

    def cancel_repeat(self):
        if self.repeat_source:
            GLib.source_remove(self.repeat_source)
            self.repeat_source = None
        self.repeat_key = None

    def start_repeat(self, key):
        self.cancel_repeat()
        if not self.repeat or key in (29,42,54,56,58,97,99,100,125,126):
            return
        self.repeat_key = key
        def tick(first=False):
            self.repeat_source = None
            if self.active is None or key not in self.keys:
                return False
            try:
                code,char = self.keys[key]
                self.phone.key(code,char,False)
                self.phone.key(code,char,True)
                self.repeat_source = GLib.timeout_add(40,tick)
            except Exception as exc:
                self.failed(str(exc))
            return False
        self.repeat_source = GLib.timeout_add(500,tick)

    def paste_text(self, text):
        if self.active is not None:
            self.phone.text(text)
            return
        # The original IME is switched on by the enter event. Give Android time
        # to bind it when pasting from the desktop window outside capture.
        self.phone.enter(True)
        self.temporary_entry = True
        def commit():
            try:
                self.phone.text(text)
                def leave():
                    try:
                        if self.active is None:
                            self.phone.enter(False)
                            self.temporary_entry = False
                    except Exception as exc: self.failed(str(exc))
                    return False
                self.sources.append(GLib.timeout_add(300,leave))
            except Exception as exc: self.failed(str(exc))
            return False
        self.sources.append(GLib.timeout_add(600,commit))

    def input(self, kind, data, sequence):
        if kind == 'disconnect':
            self.failed('libei connection closed')
            return
        if self.active is None or sequence != self.active:
            return
        try:
            if kind == 'motion':
                nx,ny = self.x+data[0]*self.speed,self.y+data[1]*self.speed
                back = {'right':nx<0,'left':nx>=self.phone.width,
                        'bottom':ny<0,'top':ny>=self.phone.height}[self.edge]
                if back:
                    self.release()
                    return
                self.x=max(0,min(self.phone.width-1,nx))
                self.y=max(0,min(self.phone.height-1,ny))
                self.phone.move(self.x,self.y)
            elif kind == 'button':
                code,down=data
                if code == 273: # Android Back on right click.
                    self.phone.key(4,0,down)
                    if down: self.keys[-1]=(4,0)
                    else: self.keys.pop(-1,None)
                elif code == 272:
                    self.phone.button(1,down,self.x,self.y)
                    if down: self.buttons.add(1)
                    else: self.buttons.discard(1)
            elif kind == 'scroll':
                self.scroll_x -= data[0]
                self.scroll_y -= data[1]
                dx,dy=int(self.scroll_x),int(self.scroll_y)
                if dx or dy:
                    self.phone.scroll(self.x,self.y,dx,dy)
                    self.scroll_x-=dx
                    self.scroll_y-=dy
            elif kind == 'key':
                key,char,down=data
                if down: self.physical_keys.add(key)
                else: self.physical_keys.discard(key)
                if down and key == 1 and any(k in self.physical_keys for k in (29,97)) and any(k in self.physical_keys for k in (56,100)) and any(k in self.physical_keys for k in (42,54)):
                    self.release()
                    return
                code=KEYS.get(key,0)
                # DeskDock treats nonzero characters as IME text. Match the
                # original server: control keys must use native Android events.
                if char < 32 or 127 <= char <= 159 or 0xfff0 <= char <= 0xffff:
                    char=0
                if down:
                    if char > 65535:
                        self.phone.text(chr(char))
                        return
                    self.keys[key]=(code,char)
                else:
                    code,char=self.keys.pop(key,(code,char))
                self.phone.key(code,char,down)
                if down: self.start_repeat(key)
                elif self.repeat_key == key: self.cancel_repeat()
        except Exception as exc:
            self.failed(str(exc))

    def drain(self, fd, condition):
        try:
            self.receiver.drain()
        except Exception as exc:
            self.failed(str(exc))
            return False
        return True

    def run(self):
        p=self.portal
        try:
            for sig in (signal.SIGINT,signal.SIGTERM):
                self.sources.append(GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,sig,self.stop))
            self.notify(type="permission")
            p.start()
            for name in ('Activated','Deactivated','Disabled','ZonesChanged'):
                self.matches.append(p.bus.add_signal_receiver(
                    lambda session,opts,n=name:self.signal(n,session,opts), signal_name=name,
                    dbus_interface=INTERFACE, path=PATH, bus_name=SERVICE))
            self.matches.append(p.bus.add_signal_receiver(lambda *args:self.failed('Portal session closed'),
                signal_name='Closed', dbus_interface='org.freedesktop.portal.Session', path=p.session, bus_name=SERVICE))
            fd=p.api.ConnectToEIS(p.session,dbus.Dictionary({},signature='sv')).take()
            self.receiver=Receiver(fd,self.input)
            self.sources.append(GLib.io_add_watch(self.receiver.fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,self.drain))
            self.receiver.drain()
            self.cursor=Cursor(p.bus)
            self.zones()
            if not self.failure and not self.stopping:
                self.loop.run()
            if self.failure:
                raise RuntimeError(self.failure)
        finally:
            try:
                self.release()
                if self.temporary_entry: self.clear()
            finally:
                for match in self.matches: match.remove()
                for source in self.sources:
                    if GLib.MainContext.default().find_source_by_id(source): GLib.source_remove(source)
                self.cancel_repeat()
                try:
                    if self.receiver: self.receiver.close()
                finally:
                    p.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop-worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--no-repeat',action='store_true',help='Disable key auto-repeat')
    parser.add_argument('--check',action='store_true',help='Check Wayland support without requesting input capture')
    parser.add_argument('--serial',help='adb serial (required when multiple devices are attached)')
    parser.add_argument('--edge',choices=['left','right','top','bottom'],default='right')
    parser.add_argument('--speed',type=float,default=1.0)
    args=parser.parse_args()
    if not 0 < args.speed <= 10:
        parser.error('--speed must be greater than 0 and at most 10')
    def notify(**event):
        if args.desktop_worker:
            print('@event '+json.dumps(event),flush=True)
    phone=Phone(args.serial)
    phone.on_clipboard = lambda text: notify(type='clipboard',text=text)
    host=None
    def early_stop(signum, frame):
        if host: host.stop()
        else: raise KeyboardInterrupt
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,early_stop)
    portal=None
    try:
        portal=Portal()
        if portal.capabilities & 3 != 3:
            raise RuntimeError('InputCapture portal lacks keyboard/pointer support')
        if args.check:
            import ctypes
            ctypes.CDLL('libei.so.1'); ctypes.CDLL('libxkbcommon.so.0')
            print(f'InputCapture v{portal.version}, keyboard and pointer supported; libei and xkbcommon available.')
            return 0
        notify(type='connecting')
        phone.launch()
        phone.connect()
        phone.wait_agent()
        host=Host(phone,portal,args.edge,args.speed,notify=notify,repeat=not args.no_repeat)
        if args.desktop_worker:
            def commands():
                for line in sys.stdin:
                    try:
                        command=json.loads(line)
                        def execute(command=command):
                            try:
                                if command.get('command')=='clipboard': phone.clipboard(command['text'])
                                elif command.get('command')=='text': host.paste_text(command['text'])
                                elif command.get('command')=='release': host.release()
                                elif command.get('command')=='stop':host.stop()
                            except Exception as exc: host.failed(str(exc))
                            return False
                        GLib.idle_add(execute)
                    except (ValueError,KeyError): pass
                GLib.idle_add(host.stop)
            threading.Thread(target=commands,daemon=True).start()
        host.run()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        notify(type="error",message=str(exc))
        print(str(exc),file=sys.stderr)
        return 1
    finally:
        if portal: portal.close()
        phone.close()

if __name__ == '__main__':
    sys.exit(main())
