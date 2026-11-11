# StoryLens personal Android app

A real native Java Android application: platform widgets, `ImageView`, `VideoView` and `MediaPlayer`. No WebView, PWA, embedded website, Tailscale, phone-side model or paid service.

## Connect

1. Install the signed personal APK only after owner approval. Package: `app.storylens.phone`; Android 8/API 26 or newer.
2. In StoryLens, paste the laptop's `SL1.…` code, or select **Import connection file** and choose its private `.slconnect` text file, encoded **UTF-8 without BOM**. No QR scanner or extra app is required. Final review reproduced a BOM-prefixed-file rejection (F1); it is reported, not silently repaired after review.
3. Pairing is encrypted with a non-exportable Android Keystore AES-256-GCM key in private preferences. Backup and device transfer are excluded. The original imported connection file is outside the app: keep it private or remove it with Android Files after pairing.
4. Keep StoryLens foreground to receive replies and transfer files. Laptop jobs continue when the phone leaves the app. Return and refresh to see their saved state.

Only trusted system-certificate HTTPS `*.workers.dev` origins are accepted, without userinfo, custom ports, paths, query strings or redirects. Normal Cloudflare `worker.account.workers.dev` names are supported. No relay address, phone token or AES key is embedded in the APK. Relay/laptop deployment and actual pairing are separate parent-owned work.

## Native workflow

- Chats, new chat, General/Cricket/Gaming context, messages, real stage status and Stop.
- Each command has a fresh transport UUID. Mutations are sent once, never blindly retried. An uncertain send persists locally; **Check chat** fetches the current chat before explicitly clearing the old draft. It never repeats it automatically.
- Attach via Android's document picker; no broad storage permission. The APK requests Internet plus AndroidX's own signature-only non-exported-receiver permission; it requests no camera, microphone, storage or contacts permissions. Uploads and downloads use encrypted 128 KiB chunks. A single file above **256 MiB** is refused. Unknown-size document providers require a local copy.
- Downloaded results stay in the app's private cache. Images/audio/video use native local preview; Android-supported codecs only. PDFs/general files can be saved with Android's document creation picker or explicitly shared using a read-only `FileProvider` grant. Incoming result URLs are never loaded.
- Progress uses supplied counts only. Operations with no measured count remain indeterminate. No fabricated model results or sample conversations are shipped.
- **Forget connection** removes local pairing/cache, not laptop chats/jobs. Revoke the phone on the laptop when necessary; local forgetting is not remote token revocation.

## Build and signing

The Pocket Tracker project was inspected read-only for toolchain configuration. Its migrated SDK/JDK21/Gradle paths were absent. Missing prerequisites were verified before official isolated tooling was recovered under `toolchain/`; Pocket Tracker source, app data and keys were not copied or changed.

- Microsoft OpenJDK 21.0.13.0.2+1, Windows x64
- Gradle 8.12.1; Android Gradle Plugin 8.8.2
- Android platform 35 revision 2; build-tools 35.0.0
- Java 17 source/bytecode; AndroidX Core 1.15.0; desugar JDK libraries 2.1.4

`build.ps1` runs `:core:check :app:assembleRelease :app:lintRelease` and copies **only** the APK/hash to `output\phone-native`. Use `-Offline` after dependency resolution. It requires the machine's normal approved PowerShell script policy; no policy change is performed. On this machine direct PowerShell/native build commands were used because script-file execution is disabled.

The distinct personal RSA signing key is `.private\storylens-personal.p12`; its password is protected by Windows user DPAPI in the same ACL-restricted directory. Preserve both privately for updates; never distribute or commit them. APK distribution must exclude `.private`, toolchains, caches and local properties. Nothing installs or controls a phone automatically.

## Verification boundary

JVM protocol/foreground transport tests are written before implementation and run red then green. They cover authentication, pairing trust, tampering, identity binding, no mutation replay, chunk bounds and lifecycle close. The Python-provided AES-GCM interoperability vector is decrypted exactly; its synthetic `vector01-…` identifier is not a production UUID, so that primitive check deliberately does not relax production ID validation. Static source/manifest checks are supplementary, not device UI evidence.

A real relay/phone run, Android Keystore operation on physical hardware, SAF picker/save/share, device lifecycle and media playback remain **unverified until owner-authorized installation and pairing**. No emulator, phone install/control, local model, laptop service restart, publishing, or old browser-connection removal is part of this build. Final build/review results are in `checks\validation.json`.
