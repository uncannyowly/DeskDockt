import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from install import install,desktop_quote
from services import load_settings,save_settings,parse_devices,Worker

class ServicesTests(unittest.TestCase):
    def test_multiple_and_unauthorized_devices(self):
        devices=parse_devices('List of devices attached\npixel device product:caiman model:Pixel_10_Pro_XL transport_id:1\nother unauthorized transport_id:2\n')
        self.assertEqual([d.serial for d in devices],['pixel','other'])
        self.assertIn('Pixel 10 Pro XL',devices[0].label)
        self.assertIn('unauthorized',devices[1].label)

    def test_invalid_preferences_restore_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            for content in ('broken','[]','{"edge":"diagonal","speed":false}'):
                path.write_text(content)
                self.assertEqual(load_settings(path)['edge'],'right')
                self.assertEqual(load_settings(path)['speed'],1.0)

    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'nested'/'settings.json'
            data={'serial':'pixel','edge':'left','speed':.7,'repeat':False}
            data.update(share_clipboard=True,phone_layout=None,pairing_code='12345678',wifi_address='192.168.1.20:19674',tls_fingerprint='a'*64)
            save_settings(data,path)
            self.assertEqual(load_settings(path),data)

    def test_launcher_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='desk dock ') as directory:
            command,desktop=install(Path(directory))
            compile(command.read_text(),str(command),'exec')
            self.assertTrue(command.stat().st_mode & 0o111)
            self.assertIn('Exec='+desktop_quote(command),desktop.read_text())
            self.assertIn('Terminal=false',desktop.read_text())

    def test_worker_commands_are_json_not_shell(self):
        worker=Worker(lambda fn,*a:fn(*a),Mock())
        process=Mock();process.poll.return_value=None
        worker.process=process
        text='literal `touch /tmp/unwanted`; $HOME\n"quoted"'
        self.assertTrue(worker.send('text',text=text))
        wire=process.stdin.write.call_args.args[0]
        self.assertEqual(json.loads(wire),{'command':'text','text':text})

    def test_old_worker_exit_does_not_clear_new_worker(self):
        callback=Mock();worker=Worker(lambda fn,*a:fn(*a),callback)
        worker.process=Mock();worker.finished(Mock(),0)
        callback.assert_not_called()
        self.assertIsNotNone(worker.process)


class WorkerIntegrationTests(unittest.TestCase):
    def test_invalid_device_exits_with_actionable_error(self):
        from gi.repository import GLib
        loop=GLib.MainLoop();events=[]
        def callback(event):
            events.append(event)
            if event['type']=='exited':loop.quit()
            return False
        worker=Worker(GLib.idle_add,callback)
        worker.start('deskdock-test-missing-device','right',1,False)
        timeout=GLib.timeout_add_seconds(10,lambda:(loop.quit(),False)[1])
        try:
            loop.run()
            self.assertTrue(any(e['type']=='error' for e in events))
            self.assertTrue(any(e['type']=='exited' and e['code']!=0 for e in events))
            self.assertIsNone(worker.process)
        finally:
            worker.stop()
            if GLib.MainContext.default().find_source_by_id(timeout):GLib.source_remove(timeout)

if __name__ == "__main__": unittest.main()
