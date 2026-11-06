# La carpeta de datos de la app

Todo lo que no es código va en **`D:\Documents\Apps\<App>\`**, con `<App>` en PascalCase sin espacios ni símbolos (`KeyboardAndMouse`, `BibleVersions`). Nunca suelto en `D:\Documents\` ni dentro del repo.

```
D:\Documents\Apps\<App>\
  app.json          configuración de la app (un archivo por app, sin secretos)
  README.md         qué va en cada carpeta
  KeyStore\         upload.jks, keystore-info.json, upload_certificate.pem
  Images\           icon\, screens\<idioma>\, feature-graphic\, promo-video\
  play\             play.json, listing\, images\, changelogs\  (play-console)
  Docs\             evidencias, licencias, documentos que no son código
```

## La referencia desde el repo

En `gradle.properties` del repo (versionado, sin secretos):

```properties
appDataDir=D:/Documents/Apps/<App>
signing.keystore=KeyStore/upload.jks
signing.credential=<slug>-release-signing
signing.envPrefix=<SLUG>
signing.signDebug=true
```

- Gradle la lee directamente (`gradle/signing.gradle`); los scripts y Claude la leen con `appinit.py detect`. En otra PC con otra ruta: variable de entorno `<SLUG>_APP_DIR`.
- El `CLAUDE.md` del repo explica la carpeta, así cada sesión sabe dónde buscar imágenes, la ficha de Play o la clave.

## app.json

```json
{
  "schema": 1,
  "name": "Keyboard & Mouse",
  "slug": "keyboardmouse",
  "package": "com.erasoft.keyboardandmouse",
  "brand": "erasoft",
  "repo": { "path": "D:/Projects/Android/keyboard-and-mouse", "remote": "https://bitbucket.org/<ws>/<slug>.git",
            "workspace": "<ws>", "slug": "<slug>" },
  "language": "kotlin",
  "ui": "compose",
  "signing": { "keystore": "KeyStore/upload.jks", "alias": "upload", "credential": "keyboardmouse-release-signing",
               "env_prefix": "KEYBOARDMOUSE", "sha256": "…", "sha1": "…",
               "backup": { "bitwarden": "2026-11-06", "offline": "2026-11-06" } },
  "libs": { "dal": true, "restlog": true, "synchronizer": false, "custom-ads": false },
  "profiles": { "play": "erasoft", "cloudflare": "erasoft", "youtube": "erasoft" },
  "web": { "zone": "era-soft.app", "domain": "keyboard.era-soft.app" },
  "created": "2026-11-06"
}
```

- La escriben `appinit.py appdir` (y la completan `wire`, `bitbucket create` y `check`, que copia las huellas de `keystore-info.json`). Claude la edita a mano solo para `signing.backup` y `web.domain`.
- **Nada secreto**: ni contraseñas, ni tokens, ni la clave. Solo nombres y huellas públicas.
- Los otros skills tienen su propia configuración (`play/play.json`, `site.json`, `video.json`, `feature-graphic.json`); `app.json` es la fuente de los valores iniciales que se les pasan (paquete, perfiles, rutas). Si un valor cambia, se cambia en los dos lugares.

## Marca → paquete, web y perfiles

| Marca | Paquete | Zona web (cloudflare-site) | Desarrollador |
|---|---|---|---|
| `erasoft` | `com.erasoft.<app>` | `era-soft.app` | Erasoft |
| `timeless` | `com.timeless.<app>` | `timelesslabs.app` | Timeless Labs |
| propia | `com.<dominio>.<app>` | la zona que el usuario tenga en Cloudflare | la que diga |

- El último segmento del paquete en minúsculas, sin guiones (`keyboardandmouse`).
- Las zonas reales salen de `appinit.py profiles` (`cloudflare_zones`): si cambian, manda lo que diga ahí.

## Mover una carpeta vieja

Carpetas como `D:\Documents\BibleVersions`, `D:\Documents\ForeverNote` o `D:\Documents\Tracker` se ordenan **una app a la vez y con permiso**:

1. `appinit.py candidates "<Nombre>"` para encontrarla y `appinit.py refs "<carpeta>" --repo <repo>` para ver quién la nombra.
2. Plan para el usuario: la carpeta nueva, el mapeo de subcarpetas si alguna cambia de nombre (p. ej. `keystore\keystore.jks` → `KeyStore\` se deja con su nombre, y `signing.keystore` apunta a él), y la lista de referencias a cambiar.
3. Con su "sí": cerrar Android Studio y Gradle (`gradlew --stop`), `Move-Item "<vieja>" "D:\Documents\Apps\<App>"`, actualizar cada referencia con Edit (incluido `~/.claude/skills/play-console/apps.json` y el `site.json` del monorepo de webs), `refs` otra vez (vacío) y un build de prueba que firme.
4. Lo que no es de la app (respaldos de bases de datos personales, archivos de otro proyecto) no se mueve sin preguntar: puede ir a `Docs\` o quedarse donde está.
