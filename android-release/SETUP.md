# Configuración (otra PC, otra app u otra cuenta)

> Los comandos son para **PowerShell** (`$env:USERPROFILE`). En `cmd` se escribe `%USERPROFILE%`.

## 1. La PC

| Requisito | Comprobar |
|---|---|
| Skill `play-console` instalado y configurado (su `SETUP.md` completo: `cryptography`, `auth` del perfil) | `python "$env:USERPROFILE\.claude\skills\play-console\scripts\play.py" status --app <datos>` |
| JDK para Gradle: `JAVA_HOME`, o Android Studio instalado (se usa su `jbr` si `JAVA_HOME` no está) | `echo $env:JAVA_HOME` |
| git | `git --version` |

## 2. Cada app

1. **Registrarla en `play-console`** (`register`, `pull`): ese skill guarda el paquete → carpeta de datos, y este lo usa.
2. **Permiso de producción:** en Play Console → **Usuarios y permisos** → la cuenta de servicio → **Permisos de la app** → la app → marcar **Publicar en producción / Release to production, exclude devices, and use Play App Signing**. Sin él, publicar en producción da HTTP 403 (las pistas de prueba funcionan igual).
3. **Firma release:** el proyecto debe firmar `bundleRelease` con la **clave de subida** sin pedir contraseñas (variables de entorno o Administrador de credenciales de Windows; nunca en el repo). Comprobar con `release.py build --skip-tests`: falla con "is not signed" si no la encuentra.
4. **Versión en `build.gradle`**: `versionCode` y `versionName` literales en `defaultConfig` del módulo de la app.
5. Si algo difiere de lo normal (módulo distinto de `app`, nombre de versión que no es una fecha, otra tarea de tests), agregar la sección `"release"` al `play.json` (ver SKILL.md).
6. Probar sin publicar: `release.py plan` desde la raíz del proyecto.

## Ejemplo real

Bible Versions (`com.timeless.bible`): datos en `D:\Documents\BibleVersions\play\` (notas en `changelogs\`), proyecto `D:\Projects\Android\bible-versions`, firma en el Administrador de credenciales (`bibleversions-release-signing`, ver `SIGNING.md` del repo), perfil `timeless`.
