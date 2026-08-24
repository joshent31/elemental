# Elemental Mobile Android wrapper

This project builds one reusable `Elemental-Mobile.apk`. The APK is not tied to a customer:

- First launch asks for the customer's Frappe site URL.
- The site opens its normal login page; the wrapper never stores the user's password.
- After login, `/mobile-app` shows only Production and Gate actions allowed by the user's roles.
- **Change Site** signs out the current WebView session and lets the device connect elsewhere.

Every target site must have a compatible version of `elemental_erp` installed. Access is enforced
again on that server; installing the APK does not grant any role or document permission.

The wrapper replaces the pages' browser camera call with an embedded ZXing QR scanner. This
keeps scanning available on the current local HTTP site, where browser `getUserMedia` may be
blocked as an insecure origin. The normal page workflow and server APIs are otherwise unchanged.

## Build requirements

- JDK 17
- Android SDK Platform 34 and Build Tools 34.0.0
- `JAVA_HOME` and `ANDROID_SDK_ROOT` set for the current shell

Build the debug-signed universal APK:

```powershell
.\build_apks.ps1
```

The setup accepts HTTP for trusted local development networks, but it warns the user because login
and ERP data are unencrypted. Customer deployments should use HTTPS. A Play Store rollout should
use a private release signing key; never commit that keystore or password.

The APK requires an active connection to the chosen Frappe server. For Android and iPhone without
a native wrapper, open `https://customer-site/mobile-app` in Chrome or Safari and install the PWA.
