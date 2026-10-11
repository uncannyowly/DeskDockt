"""Optional GNOME cursor helper; capture works without the extension."""
import dbus

class Cursor:
    def __init__(self,bus):
        self.api=dbus.Interface(bus.get_object('org.gnome.Shell',
            '/io/github/deskdock/Cursor',introspect=False),'io.github.deskdock.Cursor')
        self.available=True
        self.set(False)

    def set(self,captured):
        if not self.available:return
        try:self.api.SetCaptured(dbus.Boolean(captured),timeout=2)
        except dbus.DBusException:
            self.available=False
            print('Cursor hiding helper unavailable. Log out and back in after installing DeskDock Cursor.',flush=True)
