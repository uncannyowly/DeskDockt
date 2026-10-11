# Compatibility and free distribution

The newly written desktop host and Android companion are MIT licensed. They
require no purchase, account, subscription or activation server. Pairing is local
authentication, not licensing. DeskDock by Florian Draschbacher inspired the
input-sharing behavior; no original Android code, native libraries or signing
certificate are included in the new companion. Archived original/modified APKs
keep their original ownership and are excluded from this MIT license.

## Desktop source edition

Install Python 3.10 or newer. For ADB mode, install Google's Android
platform-tools with `adb` in PATH; direct Wi-Fi does not require ADB. Then extract the complete host ZIP:

```
python -m pip install -r requirements.txt
python install.py
python launch.py
```

On Linux with an externally managed Python, use a venv with system site packages
or distribution packages instead of overriding the distribution's pip policy.

- **Windows:** Qt GUI/tray, native mouse/keyboard filters via pynput; includes a
  source installer that creates a Start Menu shortcut. Ordinary interactive
  desktops are supported; Windows secure/UAC/lock screens are not captured.
  Windows ADB USB drivers may be required for the phone.
- **macOS:** Qt GUI/menu-bar icon, Quartz event taps via pynput. Grant Accessibility
  and Input Monitoring to the packaged application, or the Python interpreter
  when running source. Works only in an unlocked interactive session.
- **Linux X11:** Qt GUI/tray and real X11 pointer/keyboard grabs with a transparent
  cursor. No GNOME, GObject, portal or libei is required. Applies to distributions
  running a real Xorg session. XWayland is not a substitute for Wayland capture.
- **Linux Wayland:** Existing GTK/libadwaita GUI and InputCapture/libei backend.
  `python launch.py --qt` selects the Qt GUI but still uses that same portal
  worker. Install the distribution's Python D-Bus/GObject, libei/xkbcommon and
  desktop portal packages. The compositor must implement InputCapture; an app
  cannot grant itself global input access on arbitrary Wayland desktops.

`python launch.py --check` checks the selected backend without grabbing input.
`python launch.py --cli --serial DEVICE --edge right` runs the capture worker.
Closing the GUI hides/minimizes it without disconnecting. Stop sharing and Quit
are explicit actions. Ctrl+Alt+Shift+Escape releases capture.

## Android companion

The new companion is a separate app: `io.github.deskdockt.android`, minimum
Android 8/API 26, compiled against Android 17/API 37.0 and targeting API 37.
It has no JNI/native libraries, Play licensing or shell input agent. The host
uses authorized ADB only for transport, file transfers and public shell IME
selection; normal gesture and keyboard delivery happens through Android public
accessibility/input-method APIs.

1. Install the new companion APK, open it and enable **desk dockt input control**
   in Android Accessibility settings. Sideloaded apps may require Allow restricted
   settings in App info first.
2. Enable USB debugging and authorize the computer. Tap **Start sharing** on
   the phone. Copy its pairing code into the desktop application's pairing field.
3. Pick the phone and desktop edge, then Start sharing. The desktop enables and
   selects the companion's keyboard through ADB. It restores the previous keyboard
   on normal disconnect, provided the user has not selected a different keyboard.
4. For direct Wi-Fi without debugging, enable the companion keyboard in Android
   settings, select it using the phone's keyboard picker, and turn on **Enable
   direct Wi-Fi connection** before starting sharing. Android 17 asks for local
   network permission. Enter the phone's address/port, pairing code and displayed
   TLS SHA-256 fingerprint in the desktop app, then choose direct Wi-Fi.
   ADB remains available at the same time, but only one active input session is
   allowed. Stop sharing before changing server options. The default Wi-Fi port
   is 19674, configurable from 1024 to 65535.
5. Wireless ADB is also supported independently: pair Android's wireless debugging
   with ADB beforehand, and use the ADB device picker.

The ADB listener is bound to Android loopback. The optional Wi-Fi listener uses
TLS 1.2 with a device-local AndroidKeyStore key and a certificate pin checked
before authentication. No cloud relay is involved. The
versioned, size-bounded protocol authenticates with a random challenge and HMAC
based on the phone's pairing code, with failed-attempt lockout. Text clipboard sharing is opt-in on both apps and event driven, with equality
guards to avoid echoes. Android reads clipboard changes through the selected
companion keyboard; manual Send clipboard remains available. Clipboard images
and files are not synchronized. Print Screen (F13 on macOS) takes a native phone
screenshot while capture is active, on Android 9 or newer. Android manages the
screenshot UI/storage and protected-content restrictions. No packet contents, typed text or pairing codes are logged. The
accessibility service does not request permission to read window contents.

The older repaired companion remains a legacy protocol fallback for existing
users. Fresh installations and distribution should use the new MIT companion.

## Packaging

Windows/macOS executables must be built on their respective systems. Install
PyInstaller, then run `python build-portable.py`. The included manually triggered
GitHub Actions workflow builds Windows, macOS and Linux X11 packages on native
runners. Unsigned macOS bundles need the usual Gatekeeper approval; no signing or
notarization is claimed. The Linux bundled edition targets X11; Wayland uses the
source edition and its distribution's portal/GObject dependencies.

Platform validation status is recorded in the release notes. A platform backend
being implemented or packaged does not mean its live behavior has been tested
on hardware that is unavailable here.
