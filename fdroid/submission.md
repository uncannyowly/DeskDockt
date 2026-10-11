# F-Droid inclusion request: desk dockt

Status: submitted for review. https://gitlab.com/fdroid/fdroiddata/-/merge_requests/52116

Submission is not approval or F-Droid availability.

App ID: io.github.deskdockt.android
License: MIT
Version: 0.2.4 (204)
Minimum Android: 8 / API 26
Target: Android 17 / API 37
Source repository: https://github.com/uncannyowly/DeskDockt
Release tag: v0.2.4, published in that repository

desk dockt is a newly written Android mouse/keyboard companion with a free Python desktop host. It supports authorized ADB and optional TLS direct Wi-Fi, screenshots, Unicode input and text clipboard sharing. It has no Google Play Services, analytics, ads, licensing server, JNI or third-party runtime dependencies. The accessibility service injects gestures and does not retrieve window contents.

The original/proprietary DeskDock APK and all reverse-engineering work products are excluded from the public release. Original authorship is credited without relicensing the original software.

Build from android-companion with JDK 17, Gradle 8.13, AGP 8.13.2, platforms;android-37.0 and build-tools;37.0.0:
JAVA_HOME=<JDK17> ANDROID_HOME=<SDK> ./gradlew assembleRelease lint
Unsigned output: app/build/outputs/apk/release/app-release-unsigned.apk

Local Android release/debug builds and lint pass. F-Droid buildserver compatibility has not been tested; the Android 17 SDK/package availability must be checked in its CI. F-Droid signs its own builds unless reproducible upstream-signature verification is configured; do not claim sideload/F-Droid signature interchangeability.

Listing text, icon, four real Android 15 emulator screenshots and changelog 204 are in android-companion/fastlane/metadata/android/en-US.

References:
https://f-droid.org/docs/Submitting_to_F-Droid_Quick_Start_Guide/
https://f-droid.org/docs/Inclusion_Policy/
Submission queue: https://gitlab.com/fdroid/rfp/-/issues/new
Metadata MR: https://gitlab.com/fdroid/fdroiddata/-/merge_requests/new
