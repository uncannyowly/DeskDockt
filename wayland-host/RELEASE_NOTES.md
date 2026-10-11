# desk dockt 0.2.0

## New implementation

- Independently written MIT Android companion, package
  `io.github.deskdockt.android`, minimum API 26/Android 8, target API 37/Android 17.
  No old APK classes, native libraries, license checks or activation server.
- USB/wireless ADB forwarding and optional direct TLS Wi-Fi server. Wi-Fi port is
  configurable (default 19674). Android 17 local-network permission is requested.
  Wi-Fi requires the phone-displayed certificate SHA-256 fingerprint and pairing
  code, plus manual keyboard selection. ADB stays available concurrently; one
  desktop input session is accepted at a time.
- Windows/macOS native filters, Qt GUI/tray and source installers. Linux X11
  capture with transparent cursor; existing Wayland portal/libei backend retained.
- Print Screen/F13 takes a native Android screenshot during phone capture (9+).
- Opt-in bidirectional text clipboard sharing through change notifications, with
  equality guards. Android reads changes through its selected input method.
- Main-thread Android replies use a bounded background writer. Input command
  backlog and frame lengths are bounded. Typed text and pairing codes are not logged.
- Closing/minimizing the host preserves sharing. Explicit Quit/Stop end it.

## Verification

- Android debug/release builds and lint pass against SDK android-37.0/Build Tools
  37.0.0 with JDK 17. Release signature verifies; APK contains no native libraries.
- Android 17/API 37 emulator, 16 KB pages: authenticated ADB transport, actual
  gesture clicks, Unicode typing, Backspace, clipboard delivery, native screenshot
  saving and previous-keyboard restoration pass.
- Direct Wi-Fi TLS listener passes certificate-pinned authentication, clicks,
  typing, Backspace and clipboard delivery through the emulator's redirected
  network port. The Python connection is checked to invoke no ADB commands.
  Emulator setup itself uses ADB to simulate native user permission/keyboard setup.
- Python suite and isolated X11/Qt tests cover capture/release, held-input cleanup,
  keyboard maps, protocol framing/pairing, real TLS pin rejection, clipboard echo
  prevention, settings and worker commands. Test logs remain in the development
  checkout's `work/`; they are excluded from release source archives.
- Linux X11 PyInstaller packaging and GUI launch pass locally. Windows/macOS
  packaging workflow is provided, but those builds have not run here.
- GNOME Wayland repeated edge crossings/returns were confirmed by the user with
  the earlier companion. New-companion live GNOME and physical Pixel tests remain.

## Limits

The Android 17 emulator's SurfaceFlinger crashed in region/luminance sampling
before running the app; setting `debug.sf.luma_sampling=0` on that test emulator
allowed testing. This is an emulator fixture workaround, not an app requirement
or a claim of validation on a physical Android 17 phone.

Windows/macOS live input capture still needs hardware validation. Wayland needs
compositor InputCapture support; universal compositor support is not promised.
Native packages are OS-specific and unsigned/unnotarized unless a distributor
signs them. Linux bundles depend on the build system's libc; source installation
is the distribution-portable route. macOS/Windows GUI availability also depends
on the supported OS versions of the installed Qt/PySide6 release.

Clipboard images/files, full compose/dead-key input, multi-phone layouts,
automatic reconnect and desktop video streaming are not implemented. File
transfer requires ADB. Wi-Fi users select and restore their keyboard manually.
Clipboard availability during Wayland capture depends on the compositor.
