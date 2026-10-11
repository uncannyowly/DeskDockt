"""GTK3 tray helper for the GTK4 desktop app (separate GTK runtimes)."""
import gi
gi.require_version('Gtk','3.0')
gi.require_version('AyatanaAppIndicator3','0.1')
from gi.repository import Gtk, Gio, GLib, AyatanaAppIndicator3 as Indicator
from branding import NAME, ICON_PATH

def main():
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    watcher=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus',
        'org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',('org.kde.StatusNotifierWatcher',)),
        GLib.VariantType.new('(b)'),Gio.DBusCallFlags.NONE,3000,None)
    if not watcher.unpack()[0]:return 1
    actions=Gio.DBusActionGroup.get(bus,'io.github.deskdock.PythonHost','/io/github/deskdock/PythonHost')
    indicator=Indicator.Indicator.new('desk-dockt',str(ICON_PATH),Indicator.IndicatorCategory.APPLICATION_STATUS)
    indicator.set_title(NAME)
    menu=Gtk.Menu()
    show=Gtk.MenuItem(label='Show '+NAME)
    show.connect('activate',lambda *_:actions.activate_action('show',None));menu.append(show)
    sharing=Gtk.MenuItem(label='Start sharing');menu.append(sharing)
    def sharing_action():
        state=actions.get_action_state('sharing')
        return 'stop' if state is not None and state.unpack() else 'start'
    def refresh(*_):
        name=sharing_action()
        sharing.set_label('Stop sharing' if name=='stop' else 'Start sharing')
        sharing.set_sensitive(actions.get_action_enabled(name))
    sharing.connect('activate',lambda *_:actions.activate_action(sharing_action(),None))
    quit_item=Gtk.MenuItem(label='Quit '+NAME)
    quit_item.connect('activate',lambda *_:actions.activate_action('quit',None));menu.append(quit_item)
    for signal in ('action-added','action-removed','action-enabled-changed','action-state-changed'):
        actions.connect(signal,refresh)
    refresh()
    menu.show_all();indicator.set_menu(menu)
    indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
    print('READY',flush=True)
    Gtk.main()
    return 0

if __name__=='__main__':raise SystemExit(main())
