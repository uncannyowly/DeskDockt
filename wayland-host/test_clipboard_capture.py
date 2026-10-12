"""Clipboard transitions without reading the user's desktop clipboard."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from app import App

class ClipboardCaptureTests(unittest.TestCase):
    def state(self):
        return SimpleNamespace(clip_sync=Mock(get_active=Mock(return_value=True)),
            worker=Mock(),connected=True,clipboard_generation=0,
            phone_clipboard='same',desktop_clipboard=None)
    def test_entry_forces_resend_and_failed_send_does_not_poison_cache(self):
        state=self.state();clipboard=Mock();clipboard.read_text_finish.return_value='same'
        App.clipboard_changed(state,clipboard,force=True)
        clipboard.read_text_async.call_args.args[1](clipboard,None)
        state.worker.send.assert_called_once_with('clipboard',text='same')
        state.worker.send.return_value=False;clipboard.read_text_finish.return_value='new'
        App.clipboard_changed(state,clipboard)
        clipboard.read_text_async.call_args.args[1](clipboard,None)
        self.assertEqual(state.phone_clipboard,'same')
        self.assertEqual(state.desktop_clipboard,'new')
    def test_disabling_while_read_is_pending_does_not_send(self):
        state=self.state();clipboard=Mock();clipboard.read_text_finish.return_value='private'
        App.clipboard_changed(state,clipboard,force=True)
        state.clip_sync.get_active.return_value=False
        clipboard.read_text_async.call_args.args[1](clipboard,None)
        state.worker.send.assert_not_called()
        self.assertIsNone(state.desktop_clipboard)
    def test_stale_async_read_cannot_overwrite_newer_text(self):
        state=self.state();clipboard=Mock();clipboard.read_text_finish.return_value='old'
        App.clipboard_changed(state,clipboard);old=clipboard.read_text_async.call_args.args[1]
        App.clipboard_changed(state,clipboard)
        old(clipboard,None);state.worker.send.assert_not_called()
    def test_disconnected_copy_is_cached_for_entry_without_sending(self):
        state=self.state();state.connected=False;clipboard=Mock();clipboard.read_text_finish.return_value='ready for paste'
        App.clipboard_changed(state,clipboard)
        clipboard.read_text_async.call_args.args[1](clipboard,None)
        self.assertEqual(state.desktop_clipboard,'ready for paste');state.worker.send.assert_not_called()
