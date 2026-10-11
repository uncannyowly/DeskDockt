"""Run only on an isolated Xvfb: DESK_DOCKT_TEST_X11=1 python -m unittest test_x11."""
import os
import unittest

@unittest.skipUnless(os.environ.get('DESK_DOCKT_TEST_X11')=='1','Requires explicitly selected isolated X11 display')
class X11Tests(unittest.TestCase):
    def test_real_grabs_keys_and_release(self):
        from backend_x11 import Backend
        from Xlib import X,display
        from Xlib.ext import xtest
        events=[];backend=Backend(lambda kind,data:events.append((kind,data)))
        peer=display.Display();root=peer.screen().root
        try:
            backend.capture()
            self.assertEqual(root.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime),X.AlreadyGrabbed)
            xtest.fake_input(peer,X.KeyPress,38);xtest.fake_input(peer,X.KeyRelease,38);peer.sync();backend.poll()
            self.assertIn(('key',(29,97,True)),events);self.assertIn(('key',(29,97,False)),events)
            backend.release((100,100))
            self.assertEqual(root.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime),X.GrabSuccess)
            peer.ungrab_keyboard(X.CurrentTime);peer.sync()
        finally:backend.close();peer.close()
