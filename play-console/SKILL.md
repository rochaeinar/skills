---
name: play-console
description: Administra apps en Google Play Console desde archivos, para varias cuentas de desarrollador - la ficha de Play Store por idioma (título, descripción breve y completa, video de YouTube, ícono, imagen destacada, capturas), subir el AAB y publicar versiones en prueba interna, cerrada, abierta o producción con notas de versión y lanzamiento escalonado, promover entre pistas, y guiar el primer lanzamiento de una app nueva. Úsalo cuando pidan "actualizar la ficha de Play", "subir capturas / descripción", "publicar una versión", "subir el AAB", "notas de la versión", "lanzamiento escalonado", "promover a producción", "estado en Play Console" o "publicar una app nueva".
---

# Google Play Console

**Antes del primer uso en una PC o cuenta de desarrollador nueva: `SETUP.md`.**

Todo pasa por `scripts/play.py` (ejecutarlo con `python`, **sin `-I`**: usa el paquete `cryptography` del sitio de usuario). Usa la API oficial (Google Play Android Developer API v3) con una **cuenta de servicio por cuenta de desarrollador** (perfil); su clave está en el Administrador de credenciales de Windows como `PlayConsole@<perfil>` (en otros sistemas: variable `PLAY_KEY_<PERFIL>` con el JSON).

## Dónde están los datos de cada app

- El skill es global; los datos de cada app están en **su propia carpeta**, fuera del repo (p. ej. `D:/Documents/<App>/play/`), descrita por `play.json`.
- `apps.json` (junto al skill, solo en esta PC) registra paquete → carpeta. Se encuentra la app por `--app <carpeta>`, o por el `applicationId` del proyecto Android de la carpeta actual.
- `play.json`:
  ```json
  {
    "package": "com.timeless.bible",
    "profile": "timeless",
    "default_language": "es-419",
    "languages": ["es-419", "en-US"],
    "images": {
      "featureGraphic":   { "es-419": "../Images/feature-graphic/feature-graphic-es-419.png" },
      "phoneScreenshots": { "es-419": "../Images/play/es-419/phone/" }
    },
    "video": { "from": "../Images/promo-video/video.json" }
  }
  ```
  Rutas relativas a la carpeta de `play.json` o absolutas: se reutiliza lo que generan `play-feature-graphic` (imagen destacada) y `app-promo-video` (enlace de YouTube que guarda `publish.py`).
- Archivos (los crea `pull` a partir de lo publicado):
  ```
  listing/<lang>/title.txt (≤30), short.txt (≤80), full.txt (≤4000), video.txt
  images/<lang>/icon.png (512×512), featureGraphic.png (1024×500, sin alfa), phoneScreenshots/01.png …
  changelogs/<lang>/<versionCode>.txt o default.txt (≤500)
  ```

## Comandos

| Comando | Qué hace |
|---|---|
| `register <carpeta> --package <id> --profile <perfil>` | Crea o actualiza `play.json` y registra la app en esta PC |
| `status` | Idiomas de la ficha y versiones de cada pista (interna, cerrada, abierta, producción) con su % |
| `pull [--images]` | **Descarga la ficha publicada** a los archivos. Empezar siempre por aquí con una app existente |
| `diff` | Qué cambiaría `push-listing`: textos (antes → después) e imágenes (por SHA-256) |
| `push-listing [--yes]` | Sube solo lo que cambió |
| `release <app.aab> [--track internal] [--rollout 0.1] [--yes]` | Sube el AAB y lo pone en una pista con las notas de `changelogs/` |
| `promote --from internal --to production [--rollout 0.1] [--yes]` | Pasa la versión de una pista a otra |

## Reglas

- **Nada se publica sin `--yes`.** Cada cambio se arma en una *edición* (borrador), Google la **valida** y se muestra; sin `--yes` se descarta. Mostrar siempre el `diff` o el resumen al usuario y pedir confirmación antes de repetir con `--yes`.
- **Producción:** solo cuando el usuario lo pide explícitamente. Preferir lanzamiento escalonado (`--rollout 0.1` = 10 %) y subirlo después con `promote` o un nuevo `release`.
- Toda afirmación de la ficha (p. ej. "hasta 4 versiones") se verifica en el código de la app.
- Las capturas deben ser reales y sin defectos (textos rotos, idioma equivocado, datos personales). Revisarlas con Read antes de subirlas.
- Respetar el perfil de cada app: nunca usar `--app` de una cuenta con las claves de otra.

## Primer lanzamiento de una app nueva

La API no crea apps. Orden:

1. **A mano en Play Console** (cuenta del perfil): *Crear app* (nombre, idioma por defecto, app/juego, gratis/pago, declaraciones). Completar **Configura tu app**: acceso a la app, anuncios, clasificación de contenido, público objetivo, política de privacidad (URL), seguridad de los datos, apps gubernamentales, servicios financieros, salud.
2. **A mano:** la **primera subida del AAB** (según las herramientas de publicación, la API solo funciona después de que exista una primera versión): *Prueba interna → Crear versión* con el AAB firmado (`./gradlew bundleRelease`).
3. `register` + `pull` (crea la estructura con lo que haya) → completar `listing/`, `images/` → `diff` → `push-listing --yes`.
4. Siguientes versiones: `changelogs/<lang>/<versionCode>.txt` → `release <aab> --track internal --yes` → probar → `promote --from internal --to production --rollout 0.1 --yes`.

## Errores frecuentes

| Error | Causa |
|---|---|
| HTTP 403 | La cuenta de servicio no está invitada en Play Console o no tiene permiso para esa app (SETUP.md paso 3). Los permisos nuevos pueden tardar en activarse |
| HTTP 404 al abrir la edición | La app no existe en esa cuenta, o aún no tiene su primera versión subida a mano |
| "No key for the profile" | Falta `play.py auth` para ese perfil en esta PC |
| Validación de imágenes | Tamaños de Play: ícono 512×512, imagen destacada 1024×500 sin alfa, capturas de 2 a 8 por tipo con lados de 320 a 3840 px (la proporción la valida Google al preparar la edición) |

## Archivos

- `scripts/play.py`, `SETUP.md`. `apps.json` se crea solo (es por PC; no se copia al respaldo).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
