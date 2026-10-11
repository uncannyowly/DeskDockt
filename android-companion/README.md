# desk dockt Android companion

A new MIT-licensed implementation, inspired by DeskDock's input-sharing workflow.
Package: `io.github.deskdockt.android`; minimum Android 8/API 26; target Android
17/API 37. Pure Java/public Android APIs, with no JNI libraries or licensing server.

Enable input control in Accessibility settings, authorize your computer for USB
(or paired wireless) debugging, and tap Start sharing. ADB requires no app pairing code. Configure optional Wi-Fi in Settings. The host selects this app's keyboard through authorized
ADB and restores your previous keyboard when it disconnects normally.

Print Screen takes a native Android screenshot on Android 9+. Enable Share text
clipboard while connected on both apps to synchronize text clipboard changes.
The selected input method listens for clipboard changes; an accessibility service
alone does not have unrestricted background clipboard access. Manual Send phone
clipboard remains available in the foreground app.

## Build

Install JDK 17 and Android SDK platform `platforms;android-37.0` plus Build Tools
37.0.0. Point ANDROID_HOME to your SDK and use:

```
./gradlew assembleDebug lint
./gradlew assembleRelease
```

Release APKs are unsigned by default. Sign with your own keystore and preserve
that key for future updates. Never distribute private keys. Windows uses
`gradlew.bat`. No SDK `local.properties` or private keystore is required in source.

ADB uses the local loopback listener. Optional direct Wi-Fi uses a configurable
TLS port (default 19674), with a device-local AndroidKeyStore certificate. Copy
the displayed SHA-256 fingerprint into the desktop app to verify its identity.
Direct Wi-Fi needs no ADB: enable/select the companion keyboard manually and
grant Android 17 local-network permission when asked. ADB remains available;
only one active desktop session is accepted. Stop sharing to change server options.

The server uses a versioned, length-bounded JSON protocol,
random challenge/HMAC pairing authentication and failed-attempt lockout. It supports ADB forwarding and opt-in authenticated TLS on the LAN. Input contents and
pairing secrets are not logged. Accessibility does not request window-content
access. The server runs as a visible connected-device foreground service.

## Simple startup (0.2.1)

The home screen offers Start/Stop sharing and Settings. USB/ADB is always available and relies on authorized USB debugging; no app pairing code is required. Wi-Fi is disabled by default. Its saved setup, port, pairing code, certificate fingerprint and keyboard picker live in Settings. Connection changes apply on the next sharing start.

Enable **Connect on start** in Settings to prepare sharing whenever you launch the app. This choice is saved. It requires Android accessibility permission and does not start the app at device boot. Manually stopping sharing suppresses automatic restart for that launch.

## Android setup shortcuts (0.2.2)

When USB debugging is off, the home screen offers **Set up USB debugging**. It opens Developer options, or About phone with Build number instructions when Developer options are not enabled. Settings also offers input control, notifications, optional Wi-Fi network settings and keyboard setup. Shortcuts open Android screens; the user still enables settings and grants permissions.

## Welcome setup (0.2.3)

New users choose **LOCAL (cable)** or **WiFi (net)**, then follow the relevant input-control, debugging or keyboard setup shortcuts. Completion and connection choice are saved. Wi-Fi setup opens pairing details in Settings; ADB stays available. Existing installs keep their preferences. Reopen the guide through **Settings → Connection setup guide**.

## Switch connection (0.2.4)

The home screen, Settings and setup steps offer **Other connection** to open the opposite connection setup. Finish to save the new choice. If sharing is active, the phone listener restarts and the desktop must reconnect. Cable/ADB remains available when Wi-Fi is enabled.
