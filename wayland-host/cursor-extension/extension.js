import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const XML = `<node><interface name="io.github.deskdock.Cursor">
<method name="SetCaptured"><arg type="b" direction="in"/></method>
</interface></node>`;

export default class DeskDockCursor extends Extension {
    enable() {
        this._owners = new Set();
        this._tracker = global.backend.get_cursor_tracker();
        this._object = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._object.export(Gio.DBus.session, '/io/github/deskdock/Cursor');
        this._subscription = Gio.DBus.session.signal_subscribe(
            'org.freedesktop.DBus', 'org.freedesktop.DBus', 'NameOwnerChanged',
            '/org/freedesktop/DBus', null, Gio.DBusSignalFlags.NONE,
            (_connection, _sender, _path, _interface, _signal, parameters) => {
                const [name, , owner] = parameters.deep_unpack();
                if (!owner)
                    this._release(name);
            });
    }

    SetCapturedAsync([captured], invocation) {
        const owner = invocation.get_sender();
        if (captured && !this._owners.has(owner)) {
            if (this._owners.size === 0)
                this._tracker.inhibit_cursor_visibility();
            this._owners.add(owner);
        } else if (!captured) {
            this._release(owner);
        }
        invocation.return_value(new GLib.Variant('()', []));
    }

    _release(owner) {
        if (this._owners.delete(owner) && this._owners.size === 0)
            this._tracker.uninhibit_cursor_visibility();
    }

    disable() {
        Gio.DBus.session.signal_unsubscribe(this._subscription);
        this._object.unexport();
        if (this._owners.size > 0)
            this._tracker.uninhibit_cursor_visibility();
        this._owners.clear();
        this._object = null;
        this._tracker = null;
    }
}
