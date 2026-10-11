from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from app import App
from services import Device

class TrayTests(unittest.TestCase):
    def test_closing_window_hides_without_stopping_sharing(self):
        state=SimpleNamespace(tray_ready=True,hide_window=Mock(),close=Mock())
        self.assertTrue(App.window_closed(state))
        state.hide_window.assert_called_once()
        state.close.assert_not_called()

    def test_missing_tray_minimizes_without_stopping_sharing(self):
        state=SimpleNamespace(tray_ready=False,window=Mock(),close=Mock(),hide_window=Mock())
        App.hide_window(state)
        state.window.set_visible.assert_not_called()
        state.window.minimize.assert_called_once()
        self.assertTrue(App.window_closed(state))
        state.close.assert_not_called()

class ConnectRequestTests(unittest.TestCase):
    def state(self):
        return SimpleNamespace(requested_serial='phone',window=True,supported=True,
            worker=SimpleNamespace(process=None),devices=[Device('phone','device','Android')],
            device=Mock(),start_clicked=Mock(),toast=Mock())

    def test_ready_requested_device_starts_once(self):
        state=self.state()
        App.start_requested(state)
        self.assertIsNone(state.requested_serial)
        state.start_clicked.assert_called_once()
        App.start_requested(state)
        state.start_clicked.assert_called_once()

    def test_waits_for_authorized_device(self):
        state=self.state();state.devices=[Device('phone','unauthorized','Android')]
        App.start_requested(state)
        self.assertEqual(state.requested_serial,'phone')
        state.start_clicked.assert_not_called()

    def test_never_selects_another_connected_device(self):
        state=self.state();state.devices=[Device('other','device','Android')]
        App.start_requested(state)
        state.start_clicked.assert_not_called()

    def test_does_not_start_duplicate_worker(self):
        state=self.state();state.worker.process=Mock()
        App.start_requested(state)
        state.start_clicked.assert_not_called()
        state.toast.assert_called_once()

if __name__=='__main__':unittest.main()
