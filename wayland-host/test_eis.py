"""Exercise the real libei ABI against an isolated libeis server, no desktop capture."""
import ctypes as C
import time
import os
import unittest
from eis import Receiver,bind,P,I,U,D

class EISTests(unittest.TestCase):
    def test_receiver_motion_and_button(self):
        lib=C.CDLL('libeis.so.1')
        signatures={
            'new':(P,P),'setup_backend_fd':(I,P),'backend_fd_add_client':(I,P),
            'dispatch':(None,P),'get_event':(P,P),'event_get_type':(I,P),
            'event_get_client':(P,P),'event_get_seat':(P,P),'event_unref':(P,P),
            'client_connect':(None,P),'client_new_seat':(P,P,C.c_char_p),
            'seat_configure_capability':(None,P,I),'seat_add':(None,P),
            'seat_new_device':(P,P),'device_configure_type':(None,P,I),
            'device_configure_name':(None,P,C.c_char_p),'device_configure_capability':(None,P,I),
            'device_add':(None,P),'device_resume':(None,P),'device_start_emulating':(None,P,U),
            'device_pointer_motion':(None,P,D,D),'device_button_button':(None,P,U,C.c_bool),
            'device_frame':(None,P,C.c_uint64),'unref':(P,P),
            'device_new_keymap':(P,P,I,I,C.c_size_t),'keymap_add':(None,P),
            'device_keyboard_key':(None,P,U,C.c_bool),
            'device_scroll_delta':(None,P,D,D),'device_scroll_discrete':(None,P,I,I),
        }
        for name,sig in signatures.items():bind(lib,'eis_'+name,*sig)
        ctx=lib.eis_new(None)
        self.assertEqual(lib.eis_setup_backend_fd(ctx),0)
        events=[];devices=[]
        receiver=Receiver(lib.eis_backend_fd_add_client(ctx),lambda *args:events.append(args))
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                lib.eis_dispatch(ctx)
                while event:=lib.eis_get_event(ctx):
                    kind=lib.eis_event_get_type(event)
                    if kind==1:
                        client=lib.eis_event_get_client(event)
                        lib.eis_client_connect(client)
                        seat=lib.eis_client_new_seat(client,b'test')
                        for cap in (1,4,16,32):lib.eis_seat_configure_capability(seat,cap)
                        lib.eis_seat_add(seat)
                    elif kind==3 and not devices:
                        device=lib.eis_seat_new_device(lib.eis_event_get_seat(event))
                        lib.eis_device_configure_type(device,1)
                        lib.eis_device_configure_name(device,b'test mouse')
                        for cap in (1,4,16,32):lib.eis_device_configure_capability(device,cap)
                        x=receiver.x
                        bind(x,'xkb_keymap_new_from_names',P,P,P,I)
                        bind(x,'xkb_keymap_get_as_string',P,P,I)
                        keymap=x.xkb_keymap_new_from_names(receiver.xcontext,None,0)
                        buffer=x.xkb_keymap_get_as_string(keymap,1)
                        text=C.string_at(buffer)+b'\0'
                        libc=C.CDLL(None);bind(libc,'free',None,P);libc.free(buffer)
                        x.xkb_keymap_unref(keymap)
                        fd=os.memfd_create('test-keymap');os.write(fd,text)
                        map_=lib.eis_device_new_keymap(device,1,fd,len(text))
                        lib.eis_keymap_add(map_);os.close(fd)
                        lib.eis_device_add(device);lib.eis_device_resume(device)
                        devices.append(device)
                    lib.eis_event_unref(event)
                receiver.drain()
                if devices and receiver.sequences=={}:
                    device=devices[0]
                    lib.eis_device_start_emulating(device,7)
                    lib.eis_device_pointer_motion(device,12.5,-3.0)
                    lib.eis_device_button_button(device,272,True)
                    lib.eis_device_keyboard_key(device,30,True)
                    lib.eis_device_scroll_delta(device,0,15)
                    lib.eis_device_scroll_discrete(device,0,120)
                    lib.eis_device_frame(device,int(time.monotonic()*1e6))
                if any(e[0]=='scroll' for e in events):break
                time.sleep(.005)
            self.assertIn(('motion',(12.5,-3.0),7),events)
            self.assertIn(('button',(272,True),7),events)
            self.assertIn(('key',(30,97,True),7),events)
            self.assertEqual([e for e in events if e[0]=='scroll'], [('scroll',(0.0,1.0),7)])
        finally:
            receiver.close();lib.eis_unref(ctx)

if __name__=='__main__':unittest.main()
