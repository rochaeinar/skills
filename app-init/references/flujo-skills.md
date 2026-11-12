# Qué deja listo app-init para cada skill

app-init va **primero** (o cuando se ordena un proyecto viejo). Cada skill posterior encuentra sus datos sin preguntar:

| Skill | Necesita | Lo deja app-init |
|---|---|---|
| `app-screen-design` | Código o texto de la app, idiomas, paleta | `CLAUDE.md` con el resumen de la app; el proyecto base |
| `app-design-implementation` | Lenguaje, librerías propias, arquitectura, Maestro | Regla de lenguaje, librerías incluidas en Gradle, `CLAUDE.md` con las reglas de arquitectura, tests y logs |
| `play-feature-graphic` | Logo, capturas, carpeta de salida | `Images/icon/`, `Images/screens/`; su config irá en `Images/feature-graphic/` |
| `app-promo-video` | Carpeta de salida, perfil de YouTube | `Images/promo-video/`; `profiles.youtube` de `app.json` → `"youtube_profile"` de `video.json` |
| `cloudflare-site` | Perfil de Cloudflare, dominio, rutas de la app, de las imágenes y de Play | `profiles.cloudflare`, `web.zone` / `web.domain`, `repo.path`, `Images/`, `play/` → argumentos de `web.py new` |
| `play-console` | `play.json` con paquete y perfil, registro en `apps.json`; en el primer lanzamiento, la clave propia por PEPK | `play.py register <App>/play --package --profile` hecho en el paso 8; `KeyStore/upload.jks` y `references/firma.md` paso 5 |
| `android-release` | Firma release sin preguntar contraseñas, `play-console` configurado | `gradle/signing.gradle` + credencial; `bundleRelease` firmado con la clave única verificado |

Valores que se copian de `app.json` cuando se use cada skill (decirlo en el resumen):
- `web.py new <slug> --profile <profiles.cloudflare> --domain <web.domain> --package <package> --name "<name>" --app-project <repo.path> --assets <carpeta>/Images`
- `video.json`: `"youtube_profile": "<profiles.youtube>"`
- `play.json`: `"profile": "<profiles.play>"` (ya escrito por `register`)

Un skill que cambie uno de estos valores (p. ej. el dominio final de la web) lo actualiza también en `app.json`.
