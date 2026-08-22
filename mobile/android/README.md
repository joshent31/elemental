# Elemental Android scan apps

This Android project builds two separately installable APKs from one secure WebView shell:

- `Elemental-Production-Scan.apk` opens `/scan-menu`.
- `Elemental-Gate-Scan.apk` opens `/gate-scan`.

Both apps use the normal Frappe login page and retain the signed-in session. Access is enforced
again on the server: Production tiles appear only for the user's assigned Elemental functional
roles, and Gate requires `Elemental HR Gate User` or `Elemental HR Gate HOD`.

The wrapper replaces the pages' browser camera call with an embedded ZXing QR scanner. This
keeps scanning available on the current local HTTP site, where browser `getUserMedia` may be
blocked as an insecure origin. The normal page workflow and server APIs are otherwise unchanged.

## Build requirements

- JDK 17
- Android SDK Platform 34 and Build Tools 34.0.0
- `JAVA_HOME` and `ANDROID_SDK_ROOT` set for the current shell

Build both debug-signed APKs for the current local server:

```powershell
.\build_apks.ps1 -ServerUrl "http://efpl-4.local:8080"
```

For phones outside the local network, rebuild with the site's HTTPS URL. HTTP login/data traffic
is unencrypted even though the native camera works, so HTTPS is also recommended on the internal
network. A production or Play Store rollout should use a private release signing key; never
commit that keystore or password.

The APKs require an active connection to the Frappe server. The Production and Gate apps may be
installed together because they use different Android application IDs.
