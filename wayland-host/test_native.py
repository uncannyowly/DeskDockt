import hashlib
import hmac
import json
import os
import socket
import struct
import threading
import unittest
from unittest.mock import Mock,patch
from native_engine import Engine
from platforms import backend_name
from protocol import Phone

class PlatformTests(unittest.TestCase):
    def test_automatic_platform_selection(self):
        for system,environment,expected in (
            ('win32',{},'windows'),('darwin',{},'macos'),
            ('linux',{'DISPLAY':':0'},'x11'),
            ('linux',{'DISPLAY':':0','WAYLAND_DISPLAY':'wayland-0'},'wayland')):
            self.assertEqual(backend_name(system=system,environ=environment),expected)

    def test_does_not_grab_xwayland(self):
        with self.assertRaises(ValueError):backend_name('x11','linux',{'WAYLAND_DISPLAY':'wayland-0'})

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.phone=Mock(width=720,height=1600)
        self.backend=Mock();self.backend.monitors.return_value=[(1920,1080,0,0)]
        self.engine=Engine(self.phone,self.backend)

    def test_desktop_keys_are_untouched_before_capture(self):
        self.engine.key(29,97,True);self.engine.button(1,True)
        self.phone.key.assert_not_called();self.phone.button.assert_not_called()

    def test_capture_and_return_releases_held_input(self):
        self.engine.position(1919,500);self.engine.key(29,97,True);self.engine.button(1,True)
        self.engine.motion(-10,0)
        self.assertFalse(self.engine.active);self.backend.release.assert_called_once()
        self.phone.key.assert_any_call(29,97,False);self.phone.button.assert_any_call(1,False,2,self.engine.y)

    def test_controls_and_native_repeat_are_normalized(self):
        self.engine.position(1919,500)
        self.engine.key(67,8,True);self.engine.key(67,8,True);self.engine.key(67,8,False)
        self.assertEqual(self.phone.key.call_count,2);self.phone.key.assert_called_with(67,0,False)

    def test_printscreen_is_sent_once_and_not_repeated(self):
        from keymap import KEYS
        from backend_hooks import VK,MAC
        self.assertEqual((KEYS[99],VK[44],MAC[105]),(120,120,120))
        self.engine.position(1919,500)
        self.engine.key(120,0,True);self.engine.key(120,0,True)
        self.engine.tick();self.engine.key(120,0,False)
        self.assertEqual(self.phone.key.call_count,2)
        self.assertIsNone(self.engine.repeat_key)

    def test_emergency_chord_and_broken_phone_restore_desktop(self):
        self.engine.position(1919,500)
        for code in (113,57,59):self.engine.key(code,0,True)
        self.phone.key.side_effect=ConnectionError('Disconnected')
        with self.assertRaises(ConnectionError):self.engine.key(111,27,True)
        self.assertFalse(self.engine.active);self.backend.release.assert_called_once()
        self.assertFalse(self.engine.keys)

class NewProtocolTests(unittest.TestCase):
    def test_authenticated_handshake_and_unicode_text(self):
        phone=Phone();phone.sock,peer=socket.socketpair();phone.pairing_code='12345678'
        phone.command=Mock(return_value='old/.IME')
        def frame(value):
            data=json.dumps(value).encode();peer.sendall(struct.pack('>I',len(data))+data)
        def read():
            length=struct.unpack('>I',peer.recv(4))[0];data=b''
            while len(data)<length:data+=peer.recv(length-len(data))
            return json.loads(data)
        received=[]
        def server():
            auth=read();received.append(auth)
            frame({'type':'ready'});received.append(read())
        thread=threading.Thread(target=server);thread.start()
        try:
            phone.connect_new({'protocol':'desk-dockt','version':2,'width':720,'height':1600,'nonce':'challenge','accessible':True})
            phone.text('π😀');thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(received[0]['proof'],hmac.new(b'12345678',b'challenge',hashlib.sha256).hexdigest())
            self.assertEqual(received[1],{'type':'text','text':'π😀'})
            self.assertTrue(phone.agent_ready.is_set())
        finally:phone.close();peer.close()

    def test_wrong_protocol_or_unapproved_phone_rejected(self):
        phone=Phone()
        with self.assertRaises(ValueError):phone.connect_new({'protocol':'unknown','version':2})
        with self.assertRaises(RuntimeError):phone.connect_new({'protocol':'desk-dockt','version':2,'accessible':False})

    def test_adb_authentication_needs_no_pairing_code(self):
        phone=Phone();phone.pairing_code='';phone.command=Mock(return_value='old/.IME')
        phone.sock,peer=socket.socketpair()
        data=json.dumps({'type':'ready'}).encode();peer.sendall(struct.pack('>I',len(data))+data)
        try:
            phone.connect_new({'protocol':'desk-dockt','version':2,'authentication':'adb','width':720,'height':1600,'accessible':True})
            length=struct.unpack('>I',peer.recv(4))[0]
            self.assertEqual(json.loads(peer.recv(length)),{'type':'authenticate','proof':''})
            self.assertTrue(phone.agent_ready.is_set())
        finally:phone.close();peer.close()

    def test_wifi_rejects_authentication_downgrade(self):
        phone=Phone();phone.wifi=True
        with self.assertRaises(ValueError):
            phone.connect_new({'protocol':'desk-dockt','version':2,'authentication':'adb','accessible':True})

    def test_old_companion_still_requires_pairing(self):
        phone=Phone();phone.pairing_code=''
        with self.assertRaises(RuntimeError):
            phone.connect_new({'protocol':'desk-dockt','version':2,'accessible':True})
