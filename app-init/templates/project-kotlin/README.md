# {{APP_NAME}}

`{{PACKAGE}}`. Kotlin + Jetpack Compose.

- Build: `./gradlew assembleDebug`; release: `./gradlew bundleRelease` (signing: `SIGNING.md`).
- App data (images, Play, keystore): `{{APP_DIR}}` (`appDataDir` in `gradle.properties`).
- Own libraries are built from source from `D:/Projects/Android/...` (`settings.gradle.kts`): clone them to the same paths to build on another PC.
- Guidance for Claude Code: `CLAUDE.md`.
