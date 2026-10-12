# desk dockt

Free mouse and keyboard sharing between your computer and Android, with a new
Python desktop host and independently written Android companion. Both are MIT
licensed. There is no activation server, account or subscription.

## Get started

Install Python 3.10+ and the dependencies below. ADB mode additionally needs
Android platform-tools (`adb` in PATH); direct Wi-Fi does not require ADB:

```sh
python -m pip install -r requirements.txt
python install.py
python launch.py
```

Linux Wayland also needs its distribution's GObject/D-Bus, GTK4/libadwaita,
libei, xkbcommon and InputCapture portal support. See [COMPATIBILITY.md](COMPATIBILITY.md)
for Windows, macOS, Linux X11 and Wayland installation and permissions.

1. Install the **new** desk dockt Android companion. Its separate package does
   not replace an existing DeskDock installation.
2. Enable the companion's input control in Android Accessibility settings.
   Enable USB debugging and authorize your computer.
3. Tap **Start sharing** on the phone, or enable **Connect on start** in Settings. ADB requires no app pairing code; optional Wi-Fi setup and pairing details are in Settings.
4. Select your ADB phone or choose direct Wi-Fi with its address/port and TLS
   fingerprint. Select the desktop edge, then start sharing. On Wayland, approve
   the compositor's capture dialog.

Cross the selected desktop edge to control Android. Return through the phone's
entry edge, or press **Ctrl+Alt+Shift+Escape**. Closing the window hides/minimizes
it and keeps sharing running; **Stop sharing** and **Quit** end the session.

## Controls

Mouse movement, clicks, dragging, scrolling, right-click Back, Unicode text,
Backspace, Escape/Back and editor keyboard shortcuts are supported. Held keys
repeat after 500 ms; disable repeat in settings if desired.

**Print Screen** takes a native screenshot on the phone while capture is active
(Android 9+). On macOS an external keyboard's Print Screen/F13 maps to this action.
Android handles saving and its screenshot UI.

Enable **Share clipboard** on both apps for automatic text sharing. The host
saves this preference and sends the current clipboard again each time you cross
into the phone, so Ctrl+V can use it without opening either app. Change
notifications keep it current between crossings; there is no polling loop.
Phone clipboard access uses the selected companion keyboard within Android's
rules. Echo guards prevent ordinary loops. On Wayland, the host caches text
while desktop clipboard access is available and refreshes it on entry; fresh
reads during capture still depend on the compositor. Only text is synchronized.
Sharing is opt-in. Disable the switch when clipboard sharing is unwanted.

### Position the phone and crossing area

Choose a monitor in the layout preview, then drag the phone around its edges.
Enable **Use positioned phone** to capture only the green overlap. Adjust
**Phone height / monitor height** to match the physical arrangement; the
portrait silhouette is representative, not an automatic physical measurement.
A phone hanging two thirds above a corner exposes only its lower third as a
crossing area. Entry maps to that same third of the phone, and return maps back
to the matching monitor position. Layout is saved; stop sharing before editing.
Turn off **Use positioned phone** for the original full-edge behavior. If the
monitor geometry changes, reposition it before sharing. Wayland compositors
may reject edges between two desktop monitors: choose an exposed outside edge.

**Paste text** sends entered text to a focused phone field. **Send file** delivers
a selected file to Android Downloads using ADB, without replacing existing files. File transfer currently requires
ADB; direct Wi-Fi supports input, screenshots and text clipboard sharing.
The host restores the previous Android keyboard on normal disconnect, unless
you selected another keyboard yourself.

## Platforms and validation

Windows/macOS native input filters and a Qt GUI/tray are implemented. Linux X11
uses real pointer/keyboard grabs; Wayland uses InputCapture/libei. The source
installer handles each platform. Native packaging is available through
`build-portable.py` and the included GitHub Actions workflow.

Live GNOME Wayland edge switching and repeated return were confirmed with the
legacy companion. The new X11 backend passes an isolated real-display capture
and release test. Windows/macOS require hardware validation; no signed/notarized
binaries or live tests on those systems are claimed. See release notes for the
new Android companion's build and device-test status.

Multi-phone layouts, full compose/dead-key input, automatic reconnection and
PC video streaming are not implemented. This is input sharing, not a video
streaming application. The archived repaired APK remains a legacy protocol
fallback; new installations use the new companion.

## Development

```sh
python launch.py --check
python launch.py --connect PHONE_SERIAL
python launch.py --cli --serial PHONE_SERIAL --edge right
python -m unittest discover -v
```

The X11 integration test is opt-in: run `DESK_DOCKT_TEST_X11=1 python -m unittest
 test_x11` **only on an isolated test display**, since it briefly grabs input.

Device discovery uses ADB's streaming device list. Clipboard sharing uses change
notifications. The X11 edge detector checks the pointer every 10 ms; Windows and
macOS receive native input callbacks. Keyboard repeat runs only during capture.

Settings use the platform's per-user application directory. The Linux launcher
is `~/.local/bin/desk-dockt`; menu/autostart IDs remain compatible with older host
installations. The Linux installer installs a GNOME cursor extension where
available, to hide and restore the local pointer during capture.
