import socket
import struct
import threading
import unittest
from unittest.mock import Mock

from host import Host, barrier
from protocol import Phone

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.phone=Mock(width=1080,height=2400)
        self.portal=Mock(session='/test')
        self.host=Host(self.phone,self.portal,'right',1,repeat=False)
        self.host.zone=(1920,1080,0,0)
        self.host.trigger_start=0;self.host.trigger_span=1080
        self.host.active=7
        self.host.x,self.host.y=3,1200

    def test_extreme_monitor_barrier(self):
        self.assertEqual(barrier([(1920,1080,0,0),(2560,1440,1920,-360)],'right'),
                         ((2560,1440,1920,-360),(4480,-360,4480,1079)))

    def test_capture_sequence_gates_stale_input(self):
        self.host.input('motion',(100,0),6)
        self.phone.move.assert_not_called()
        self.host.input('motion',(100,0),7)
        self.phone.move.assert_called_once_with(103,1200)

    def test_return_releases_held_input(self):
        self.host.input('key',(30,97,True),7)
        self.host.input('button',(272,True),7)
        self.host.input('motion',(-5,0),7)
        self.assertIsNone(self.host.active)
        self.portal.api.Release.assert_called_once()
        self.phone.key.assert_any_call(29,97,False)
        self.phone.button.assert_any_call(1,False,3,1200)
        self.phone.enter.assert_called_with(False)

    def test_return_coordinates_are_doubles_on_the_dbus_wire(self):
        import dbus
        from dbus.lowlevel import MethodCallMessage
        self.host.release()
        options=self.portal.api.Release.call_args.args[1]
        message=MethodCallMessage('org.freedesktop.portal.Desktop','/test',
                                  'org.freedesktop.portal.InputCapture','Release')
        message.append(dbus.ObjectPath('/test'),options,signature='oa{sv}')
        coordinates=message.get_args_list()[1]['cursor_position']
        self.assertTrue(all(isinstance(value,dbus.Double) for value in coordinates))

    def test_socket_failure_does_not_prevent_desktop_release(self):
        self.host.cursor=Mock()
        self.host.keys[30]=(29,97)
        self.phone.key.side_effect=ConnectionError('gone')
        with self.assertRaises(ConnectionError): self.host.release()
        self.portal.api.Release.assert_called_once()
        self.assertIsNone(self.host.active)
        self.assertFalse(self.host.keys)
        self.host.cursor.set.assert_called_with(False)

    def test_old_deactivation_does_not_end_new_capture(self):
        self.host.signal('Deactivated','/test',{'activation_id':6})
        self.assertEqual(self.host.active,7)
        self.phone.enter.assert_not_called()

    def test_emergency_chord(self):
        for key in (29,56,42,1): self.host.input('key',(key,0,True),7)
        self.portal.api.Release.assert_called_once()
        self.assertIsNone(self.host.active)

    def test_keyup_preserves_keydown_character(self):
        self.host.input('key',(30,65,True),7)
        self.host.input('key',(30,97,False),7)
        self.phone.key.assert_called_with(29,65,False)

    def test_control_keys_use_native_events_instead_of_ime_text(self):
        for key,char,code in ((14,8,67),(1,27,111),(15,9,61),(111,127,112),(30,1,29)):
            with self.subTest(key=key):
                self.phone.reset_mock()
                self.host.input('key',(key,char,True),7)
                self.host.input('key',(key,char,False),7)
                self.assertEqual(self.phone.key.call_args_list,
                                 [unittest.mock.call(code,0,True),unittest.mock.call(code,0,False)])
                self.phone.text.assert_not_called()

class ProtocolTests(unittest.TestCase):
    def test_fragmented_frames(self):
        phone=Phone()
        phone.sock,peer=socket.socketpair()
        data=struct.pack('>I',5)+b'HELLO'
        def writer():
            for byte in data: peer.send(bytes([byte]))
        thread=threading.Thread(target=writer);thread.start()
        try: self.assertEqual(phone.read(),b'HELLO')
        finally: thread.join();phone.close();peer.close()

    def test_disconnect_unblocks_input_service_startup(self):
        phone=Phone()
        phone.read=Mock(side_effect=ConnectionError('Phone disconnected'))
        phone.receive()
        self.assertTrue(phone.agent_ready.is_set())
        with self.assertRaises(ConnectionError): phone.wait_agent(timeout=0)

    def test_text_packet_commits_instead_of_composing(self):
        phone=Phone();phone.sock,peer=socket.socketpair()
        try:
            phone.text('hello')
            packet=peer.recv(100)
            size,kind=struct.unpack('>II',packet[:8])
            self.assertEqual(size,len(packet)-4)
            self.assertEqual(kind,2)
            self.assertEqual(packet[8],7)
            self.assertEqual(packet[-1],1)
        finally:phone.close();peer.close()

    def test_reject_oversized_frame(self):
        phone=Phone();phone.sock,peer=socket.socketpair()
        peer.sendall(struct.pack('>I',6*1024*1024))
        try:
            with self.assertRaises(ValueError): phone.read()
        finally: phone.close();peer.close()


class RepeatTests(unittest.TestCase):
    def test_repeat_stops_on_key_release(self):
        from gi.repository import GLib
        phone=Mock(width=1080,height=2400)
        host=Host(phone,Mock(),'right',1,repeat=True)
        host.active=7
        host.input('key',(30,97,True),7)
        loop=GLib.MainLoop()
        def finish():
            host.input('key',(30,97,False),7)
            loop.quit();return False
        GLib.timeout_add(555,finish)
        try:
            loop.run()
            self.assertGreaterEqual(phone.key.call_count,4)
            phone.key.assert_called_with(29,97,False)
            self.assertIsNone(host.repeat_source)
        finally:host.cancel_repeat()

class PasteTests(unittest.TestCase):
    def test_paste_outside_capture_temporarily_activates_phone_keyboard(self):
        from gi.repository import GLib
        phone=Mock(width=1080,height=2400)
        host=Host(phone,Mock(),'right',1,repeat=False)
        host.paste_text('π😀')
        self.assertTrue(host.temporary_entry)
        phone.enter.assert_called_once_with(True)
        loop=GLib.MainLoop()
        GLib.timeout_add(980,lambda:(loop.quit(),False)[1])
        loop.run()
        phone.text.assert_called_once_with('π😀')
        phone.enter.assert_called_with(False)
        self.assertFalse(host.temporary_entry)
        self.assertIsNone(host.active)

class CleanupTests(unittest.TestCase):
    def test_receiver_closes_before_portal_even_when_setup_fails(self):
        order=[]
        portal=Mock()
        portal.start.side_effect=RuntimeError('setup failed')
        portal.close.side_effect=lambda:order.append('portal')
        host=Host(Mock(),portal,'right',1,repeat=False)
        host.receiver=Mock()
        host.receiver.close.side_effect=lambda:order.append('receiver')
        with self.assertRaisesRegex(RuntimeError,'setup failed'):host.run()
        self.assertEqual(order,['receiver','portal'])

if __name__ == "__main__": unittest.main()
