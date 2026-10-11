# Third-party components

Project code is MIT licensed. Dependencies remain under their own licenses.

- Python: PSF license, https://www.python.org/psf/license/
- PySide6/Shiboken and Qt: LGPLv3/GPL/commercial options. This project uses
  the open-source dynamic libraries under LGPLv3. License texts are in `licenses/`.
  Qt/PySide source is available from https://code.qt.io/ and
  https://download.qt.io/official_releases/QtForPython/ . You may replace/relink
  those libraries with compatible modified versions; the project imposes no
  restriction on debugging those modifications. Source downloads use pip or
  distribution-provided libraries; the application itself remains MIT licensed.
- python-xlib: LGPLv2.1+, https://github.com/python-xlib/python-xlib
- pynput: LGPLv3, https://github.com/moses-palmer/pynput
- screeninfo: MIT, https://github.com/rr-/screeninfo
- PyObjC: MIT, https://github.com/ronaldoussoren/pyobjc
- GTK, GLib, libadwaita and libei: their respective LGPL licenses, supplied by
  Linux distributions for the Wayland source edition.
- PyInstaller: GPL with the bootloader distribution exception,
  https://pyinstaller.org/en/stable/license.html
- Android SDK/Gradle build tools: their respective upstream licenses. The included
  Gradle wrapper is Apache-2.0; see `android-companion/gradle/LICENSE.txt`.

No dependency source was relicensed. No proprietary original DeskDock APK or
original signing certificate is included in release source archives.
