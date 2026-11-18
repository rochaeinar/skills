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
    "video": { "from": "../Images/promo-video/video.json", "format": "vertical" },
    "hold": ["af"]
  }
  ```
  `video.format` (opcional, por defecto `horizontal`): qué video subido por `publish.py` va en cada ficha (el de ese idioma).
  `hold` (opcional): idiomas con archivos locales que **no se publican** (ni ficha ni notas), p. ej. mientras falta un permiso. Para publicarlos, quitarlos de `hold`.
  `lock_images` (opcional): `"<idioma>/<tipo>"` (p. ej. `"en-US/phoneScreenshots"`) que nunca se suben: imágenes hechas a mano en Play Console, que mandan sobre las locales. Antes de un `push-listing` o `publish`, revisar en el `diff` que no se reemplacen imágenes que el usuario cuida a mano.
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
| `versions` | Todo versionCode que Play conoce (versiones de cada pista y todo AAB/APK subido), en JSON. Lo usa el skill `android-release` |
| `pull [--images]` | **Descarga la ficha publicada** a los archivos. Empezar siempre por aquí con una app existente |
| `diff` | Qué cambiaría `push-listing`: textos (antes → después) e imágenes (por SHA-256) |
| `push-listing [--yes] [--only en-US,es-419] [--batch 8] [--parallel 8]` | Sube solo lo que cambió. Muchas imágenes (decenas de idiomas): `--batch 8` hace una edición por cada 8 idiomas y la confirma sola (un corte de red solo pierde su tanda; repetir el comando sigue con lo que falte, porque compara por SHA-256), `--parallel` sube las imágenes de hasta 8 idiomas a la vez (por defecto 8) y `--only` limita a esos idiomas. El registro muestra cada imagen (`[idioma] tipo 3/7 03.png (512 KB) en 4.2 s`) y cada tanda; con salida a un archivo se ve en vivo |
| `release <app.aab> [--track internal] [--rollout 0.1] [--yes]` | Sube el AAB y lo pone en una pista con las notas de `changelogs/` |
| `publish <app.aab> [--track production] [--rollout 1] [--version-code N] [--yes]` | `release` + `push-listing` en **una sola edición**: Google revisa la versión, sus notas y la ficha juntas |
| `promote --from internal --to production [--rollout 0.1] [--yes]` | Pasa la versión de una pista a otra |
| `retire --track alpha [--yes]` | Detiene (*halt*) la versión actual de una pista de prueba. Nunca producción |
| `details [--email ..] [--website ..] [--phone ..] [--language ..] [--yes]` | Datos de contacto de la ficha e idioma predeterminado |
| `data-safety <form.csv> [--yes]` | Formulario de seguridad de los datos desde el CSV exportado de Play Console (con sus ids) |
| `testers [--track alpha] [--groups a@googlegroups.com,..] [--yes]` | Grupos de Google que pueden unirse a una pista de prueba (sin `--groups` solo los muestra) |
| `release-status [--track ..] [--json]` | Estado de revisión de cada versión: borrador, sin enviar, en revisión, aprobada sin publicar, rechazada, publicada |
| `reviews [--json]` / `reviews --reply <id> --text ".." --yes` | Reseñas recientes y respuesta a una |

## Reglas

- **Nada se publica sin `--yes`.** Cada cambio se arma en una *edición* (borrador), Google la **valida** y se muestra; sin `--yes` se descarta. Mostrar siempre el `diff` o el resumen al usuario y pedir confirmación antes de repetir con `--yes`.
- **Producción:** solo cuando el usuario lo pide explícitamente. Preferir lanzamiento escalonado (`--rollout 0.1` = 10 %) y subirlo después con `promote` o un nuevo `release`.
- **Reglas de la app**: si `play.json` tiene `"rules"` (p. ej. `REGLAS-FICHA.md`), leer ese archivo antes de escribir, traducir o subir cualquier texto o imagen de la ficha, y cumplirlo. Antes de `push-listing --yes`, revisar el `diff` contra esas reglas.
- Toda afirmación de la ficha (p. ej. "hasta 4 versiones") se verifica en el código de la app.
- Las capturas deben ser reales y sin defectos (textos rotos, idioma equivocado, datos personales). Revisarlas con Read antes de subirlas.
- Respetar el perfil de cada app: nunca usar `--app` de una cuenta con las claves de otra.

## Primer lanzamiento de una app nueva

**Para publicar una app nueva usar el skill `play-launch`** (generar → revisar → ejecutar, con las pantallas sin API automatizadas en el navegador dedicado). Lo de abajo es el orden manual, por si no se usa.

La API no crea apps. Orden:

1. **A mano en Play Console** (cuenta del perfil): *Crear app* (nombre, idioma por defecto, app/juego, gratis/pago, declaraciones). Completar **Configura tu app**: acceso a la app, anuncios, clasificación de contenido, público objetivo, política de privacidad (URL), seguridad de los datos (la URL de privacidad, el sitio web y las respuestas están en `<carpeta de la app>/play/app-content.md`, que escribe `cloudflare-site` con la web de la app), apps gubernamentales, servicios financieros, salud.
2. **A mano, antes del primer AAB: la clave de firma.** Modelo de las apps del usuario: **una sola clave** (la de `KeyStore/` de la carpeta de la app) es la clave de subida y la de firma de la app. En *Integridad de la app → Firma de apps* elegir **clave propia** y subirla cifrada con PEPK (pasos en `app-init/references/firma.md`, paso 5; la contraseña la escribe el usuario en una ventana aparte). No aceptar la clave generada por Google sin preguntar.
3. **A mano:** la **primera subida del AAB** (según las herramientas de publicación, la API solo funciona después de que exista una primera versión): *Prueba interna → Crear versión* con el AAB firmado (`./gradlew bundleRelease`).
4. `register` + `pull` (crea la estructura con lo que haya) → completar `listing/`, `images/` → `diff` → `push-listing --yes`.
5. Siguientes versiones: `changelogs/<lang>/<versionCode>.txt` → `release <aab> --track internal --yes` → probar → `promote --from internal --to production --rollout 0.1 --yes`.

## Errores frecuentes

| Error | Causa |
|---|---|
| Muchos `network error ... [Errno 10054]` o `SSL: UNEXPECTED_EOF_WHILE_READING` al subir imágenes | La conexión se corta a mitad de la subida (red, router o proxy). Las imágenes usan la **subida reanudable** de Google (sesión y trozos de 256 KB; tras un corte pregunta cuántos bytes tiene Play y sigue desde ahí, espera 2^n s con azar). Si aun así hay muchos cortes: `--parallel 4` o menos (con la subida del usuario llena, más idiomas a la vez no van más rápido y se cortan más) |
| HTTP 403 | La cuenta de servicio no está invitada en Play Console o no tiene permiso para esa app (SETUP.md paso 3). Los permisos nuevos pueden tardar en activarse |
| HTTP 404 al abrir la edición | La app no existe en esa cuenta, o aún no tiene su primera versión subida a mano |
| "No key for the profile" | Falta `play.py auth` para ese perfil en esta PC |
| `retire`: "Cannot halt release, no matching in progress release found" | Solo se puede detener la versión **actual** de la pista; al detenerla, Play vuelve a mostrar la anterior y esa ya no se puede detener por API. No afecta a nadie: cada usuario recibe el versionCode más alto de las pistas donde está (normalmente el de producción). Para cerrar la pista: Play Console → Prueba cerrada → la pista → quitar los testers |
| Una lista de versiones vacía no cambia nada | Play ignora `releases: []`: una versión se retira deteniéndola (`retire`) |
| Validación de imágenes | Tamaños de Play: ícono 512×512, imagen destacada 1024×500 sin alfa, capturas de 2 a 8 por tipo con lados de 320 a 3840 px (la proporción la valida Google al preparar la edición) |

## Archivos

- `scripts/play.py`, `SETUP.md`. `apps.json` se crea solo (es por PC; no se copia al respaldo).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
