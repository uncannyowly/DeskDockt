"""Run on an isolated X display; clipboard contents there are disposable."""
import os
import unittest
from unittest.mock import Mock,patch

@unittest.skipUnless(os.environ.get('DESK_DOCKT_TEST_X11')=='1','requires isolated X display')
class ClipboardTests(unittest.TestCase):
    def test_two_way_clipboard_and_echo_guard(self):
        from PySide6.QtWidgets import QApplication
        from qt_app import Window
        app=QApplication.instance() or QApplication([])
        with patch('qt_app.save_settings') as saved,patch('qt_app.DeviceWatcher'),patch('qt_app.Worker') as worker:
            window=Window();window.clip_sync.setChecked(True)
            QApplication.clipboard().setText('desktop π');app.processEvents()
            worker.return_value.send.assert_called_with('clipboard',text='desktop π')
            worker.return_value.send.reset_mock()
            window.worker_event({'type':'clipboard','text':'phone 😀'});app.processEvents()
            self.assertEqual(QApplication.clipboard().text(),'phone 😀')
            worker.return_value.send.assert_not_called()
            window.worker_event({'type':'active'});app.processEvents()
            worker.return_value.send.assert_called_once_with('clipboard',text='phone 😀')
            worker.return_value.send.reset_mock()
            window.clip_sync.setChecked(False)
            worker.return_value.send.assert_called_once_with('clipboard-sharing',enabled=False)
            worker.return_value.send.reset_mock()
            self.assertFalse(saved.call_args.args[0]['share_clipboard'])
            window.worker_event({'type':'active'})
            QApplication.clipboard().setText('private');app.processEvents()
            worker.return_value.send.assert_not_called()
            window.deleteLater();app.processEvents()
