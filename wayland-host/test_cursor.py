import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import dbus
from cursor import Cursor

class CursorTests(unittest.TestCase):
    def test_missing_extension_does_not_break_capture(self):
        api=Mock()
        api.SetCaptured.side_effect=dbus.DBusException('Unavailable')
        with patch('cursor.dbus.Interface',return_value=api):
            cursor=Cursor(Mock())
        cursor.set(True)
        self.assertFalse(cursor.available)
        api.SetCaptured.assert_called_once()

    @unittest.skipUnless(shutil.which('node'),'Node required for extension lifecycle test')
    def test_extension_restores_cursor_on_disconnect_and_disable(self):
        script=r'''
const fs = require('fs');
const assert = require('assert');
let hidden = 0, callback;
const tracker = {
    inhibit_cursor_visibility() { hidden++; },
    uninhibit_cursor_visibility() { hidden--; },
};
const Gio = {DBus: {session: {
    signal_subscribe(...args) { callback=args.at(-1); return 1; },
    signal_unsubscribe() {},
}}, DBusSignalFlags: {NONE: 0}, DBusExportedObject: {
    wrapJSObject() { return {export() {}, unexport() {}}; },
}};
const GLib = {Variant: class {}};
const source = fs.readFileSync(process.argv[1], 'utf8')
    .replace(/^import .*;$/gm, '').replace('export default class', 'class');
const Type = new Function('Gio', 'GLib', 'Extension', 'global',
    source+'; return DeskDockCursor;')(Gio, GLib, class {},
    {backend: {get_cursor_tracker() {return tracker;}}});
const helper = new Type();
helper.enable();
const call = (owner, active) => helper.SetCapturedAsync([active],
    {get_sender() {return owner;}, return_value() {}});
call(':1.1', true); call(':1.1', true); call(':1.2', true);
assert.equal(hidden, 1);
call(':1.1', false);
assert.equal(hidden, 1);
callback(null,null,null,null,null,{deep_unpack() {return [':1.2', ':1.2', ''];}});
assert.equal(hidden, 0);
call(':1.3', true); helper.disable();
assert.equal(hidden, 0);
'''
        subprocess.run(['node','-e',script,str(Path(__file__).with_name('cursor-extension')/'extension.js')],check=True)
