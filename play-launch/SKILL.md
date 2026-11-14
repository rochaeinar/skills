---
name: play-launch
description: Publica una app Android en Google Play casi sin intervención, en tres etapas que nunca se mezclan - 1) GENERAR todo sin tocar Play Console (análisis del build release, respuestas de todas las declaraciones con evidencia en el código y la regla de Google, textos de la ficha y de las declaraciones, capturas, imagen destacada, videos con Maestro, CSV de seguridad de los datos, AAB firmado) con controles automáticos; 2) el usuario REVISA en una página (los textos primero, editables) y aprueba, por app o en lote; 3) después de que el usuario inicia sesión, Claude EJECUTA exactamente lo aprobado - API oficial para la ficha, testers, versiones y seguridad de los datos, y scripts de Playwright en el navegador dedicado del usuario para las pantallas sin API - verificando cada pantalla y guardando evidencia; luego sigue la prueba cerrada, la solicitud de producción y la revisión de Google con un pase diario. Úsalo cuando pidan "publicar la app en Play", "lanzar una app nueva", "subir la app por primera vez", "llenar el contenido de la app / declaraciones / clasificación", "preparar todo para Play", "pipeline de publicación" o "estado de las apps en Play".
---

# Lanzar apps en Google Play (generar → revisar → ejecutar)

**Antes del primer uso en una PC o con una cuenta de desarrollador nueva: `SETUP.md`.** Plan y razones: `D:/Documents/Apps/plan-publicacion-automatica.md`.

Scripts (con `python`, **sin `-I`**: usan Playwright y `cryptography` del sitio de usuario):
- `scripts/launch.py`: expediente, análisis, controles, revisión, aprobación, estados, pase diario, políticas.
- `scripts/console.py`: el navegador dedicado (abrir, cuenta, capturas, pantallas sin API).
- `play-console/scripts/play.py`: todo lo que tiene API (ficha, imágenes, AAB, pistas, `details`, `data-safety`, `testers`, `release-status`, `reviews`).

Cada app guarda su estado en `D:/Documents/Apps/<App>/play/launch/`: `expediente.json` (todo lo que se enviará), `facts.json` (lo que dice el build), `check.json`, `approval.json`, `state.json`, `texts/`, `evidence/<fecha>/`, `console-log.txt`.

## Reglas que no cambian

- **Las etapas no se mezclan.** Nada llega a Play Console antes de la aprobación; en la etapa 3 no se genera ni se reescribe nada. Si falta algo, se vuelve a la etapa 1 para eso y a la 2 para revisarlo.
- **Fail-closed.** Toda respuesta del expediente lleva `evidence` (`archivo:línea` o salida del build) y `rule` (URL de Google). Sin las dos, `check` falla. Si una pantalla pide algo que no está en el expediente, se detiene y se pregunta: nunca se inventa una respuesta.
- **Siempre la verdad.** Las declaraciones describen lo que hace el build release, no lo que se quisiera. Una respuesta dudosa se pregunta al usuario.
- **Nada para ocultar la automatización**: ni navegadores anti-detección, ni huellas falsas, ni testers falsos o intercambiados. La sesión es la del usuario, iniciada a mano, en un navegador visible; una pestaña y una app a la vez, a ritmo humano, mismo equipo y red.
- **Nunca automatizar**: crear la cuenta, pagar, verificar la identidad, aceptar acuerdos, el inicio de sesión, ni contraseñas (la de la clave para PEPK la escribe el usuario en una ventana aparte).
- **Ritmo de una cuenta nueva** (plan §6): primero una app hasta producción, luego 1 por semana; subir el ritmo solo sin avisos de política.
- **Producción**: solo con aprobación válida y, si `production_criteria.preapproved` es `false`, con la confirmación del usuario el día 14.

## Etapa 1: generar (sin Play Console, sin la sesión del usuario)

1. `launch.py init D:/Documents/Apps/<App>`: crea el expediente y registra la app en `play-console` (perfil `profiles.play` de `app.json`).
2. Build release: `./gradlew :app:assembleRelease :app:bundleRelease` en el repo (firma de `app-init`). Escribir la ruta del AAB en `expediente.aab`.
3. `launch.py analyze --app <carpeta>`: lee el APK release con `aapt2` (permisos, servicios en primer plano, `targetSdk`) y las dependencias (inventario de `cloudflare-site`, `web.py licenses`). Deriva lo mecánico: ID de publicidad, anuncios, servicios en primer plano, permisos sensibles.
4. **Claude responde el resto** en `expediente.json`, leyendo el código de la app y la copia de la política en `policies/snapshots/` (no de memoria): `privacy_policy`, `app_access`, `content_rating` (cada respuesta del cuestionario IARC), `target_audience`, `data_safety`, `news_app`, `government_app`, `financial_features`, `health_apps`, `category`. Cada una con `value`, `evidence`, `rule` y `"status": "answered"`. Lo que dependa de una decisión del usuario (edad mínima, correo público) se le pregunta.
5. **Textos** (los escribe Claude, verificados en el código; reglas de `play-console` y `REGLAS-FICHA.md` si la app las tiene):
   - Ficha por idioma: `play/listing/<lang>/title.txt` (≤ 30), `short.txt` (≤ 80), `full.txt` (≤ 4000).
   - Notas: `play/changelogs/<lang>/default.txt` (≤ 500).
   - Declaraciones: `launch/texts/fgs-<tipo>.txt` por servicio en primer plano (y `expediente.texts.fgs_<tipo>`), `app-access.txt`, `tester-message.txt`.
6. **Recursos** (skills existentes): capturas por idioma con Maestro en `play/images/<lang>/phoneScreenshots/` (y tablets 7"/10"), ícono 512 y `featureGraphic.png` (`play-feature-graphic`), video promocional (`app-promo-video`, el gasto se aprueba en la revisión), **video de cada servicio en primer plano** (flujo Maestro del uso real + `screenrecord`, subido oculto; el enlace va en `expediente.videos.fgs_<tipo>`).
7. **Seguridad de los datos**: el CSV con los ids de Play (`launch/data-safety.csv`). La plantilla se exporta una vez desde Play Console (*App content > Data safety > Export to CSV*) y se guarda en `templates/data-safety-template.csv`; Claude la llena desde el análisis.
8. `launch.py check --app <carpeta>`: límites de caracteres, palabras prohibidas por la política de metadatos, tamaños de imágenes, declaraciones con evidencia y regla, coherencia (anuncios y analítica del build contra lo declarado, video y texto por servicio en primer plano, `targetSdk` mínimo, CSV, AAB, contacto), y que la política de privacidad responda. **Sin errores** pasa a `generated`.

## Etapa 2: revisión del usuario

1. `launch.py review-export --app <carpeta> [--app ...] --out <scratchpad>/review`: datos de la página (un documento por texto, imagen, video, declaración y la configuración) y las imágenes.
2. Publicar `templates/review.html` con la herramienta Artifact (copiarlo a la carpeta de salida; la primera vez con `icon: "checklist"`), `files` = el mapa de `files.json`, `capabilities: {db: {}, user: {}}`. Después, cargar los datos con `ArtifactData` `batch` por cada lista de `batches.json` (escrituras con `file_path`). Una sola página sirve para todas las apps del lote: actualizarla con el mismo archivo.
3. Darle el enlace al usuario. En la página ve **los textos primero**, editables, con su conteo y el idioma base al lado; marca cada texto como revisado, deja notas y aprueba por app o todas.
4. `ArtifactData list` de `items`, `apps` y `approvals` con `out_dir=<scratchpad>/review-in`, y `launch.py review-import --from <scratchpad>/review-in`: aplica los textos editados a sus archivos, guarda las notas en `review-notes.md` y registra la aprobación con el hash de todos los archivos. **Con notas no se registra la aprobación**: Claude las aplica, vuelve a correr `check` y `review-export`, y el usuario aprueba de nuevo.
5. `launch.py approval`: la aprobación vale mientras ningún archivo cambie. Cualquier cambio posterior la anula.

## Etapa 3: ejecución (después de que el usuario inicia sesión)

1. El usuario: `console.py open --profile <perfil>` e inicia sesión a mano (la primera vez además `console.py bind --profile <perfil>`). Avisa a Claude.
2. Claude: `launch.py approval` y `console.py whoami --profile <perfil>`. Si la cuenta no es la vinculada, se detiene.
3. Pantallas sin API, en este orden, cada una con `console.py run <pantalla> --app <carpeta>` (ver `screens/README.md`; una pantalla en `draft` se graba y se prueba con `--dry-run` primero): `create_app` → `bind-app` → `app_signing` (PEPK con la clave de `app-init`) → `first_aab` → `privacy_policy`, `app_access`, `ads`, `advertising_id`, `content_rating`, `target_audience`, `foreground_services`, `other_declarations`, `category`, `countries`.
4. Por API: `play.py details --email … --website … --yes`, `play.py data-safety <csv> --yes`, `play.py push-listing --yes`, `play.py testers --track alpha --groups <grupo> --yes`, `play.py release <aab> --track alpha --yes`.
5. `send_for_review` (pantalla) y `launch.py set-state closed-test`. Mensaje a los testers: `launch/texts/tester-message.txt` con el enlace de inscripción (el usuario lo envía).
6. Verificación: cada pantalla relee lo guardado (`readback`) y deja captura en `evidence/<fecha>/`. Al final, informe al usuario con las capturas y lo que quedó pendiente.

## Después: prueba cerrada, producción, revisión

- `launch.py tick` (diario, Programador de tareas; ver SETUP.md): consulta el estado de revisión por API, cuenta los días de la prueba cerrada y avisa lo que necesita al usuario. Nunca toca pantallas.
- Día 14: Claude lee el conteo de inscritos (`closed_test_count`), redacta las respuestas de la solicitud de producción a partir de la prueba real (comentarios de los testers, versiones subidas) en `launch/texts/production-answers.txt`, y con la aprobación (o la preaprobación con criterios) corre `production_request`.
- Aprobada: `play.py promote --from alpha --to production --rollout <production_rollout> --yes`, luego subir al 100 % (`android-release`).
- `launch.py status`: todas las apps y lo que espera cada una.

## Políticas

`launch.py policies fetch` (semanal, y antes de cada etapa 1): copia con fecha de cada página de `policies/sources.json` en `policies/snapshots/<id>/`. Si una cambió, `policies/changes.json` dice cuál y a qué respuestas afecta: Claude lee el cambio, revisa esas respuestas en cada app y, si cambian, la app vuelve a la etapa 2. `rules/metadata.json` (palabras prohibidas, `targetSdk` mínimo, SDK de anuncios y analítica) se actualiza con lo que digan las políticas.

## Errores frecuentes

| Error | Qué hacer |
|---|---|
| `check`: "not answered" | Responder esa declaración en el expediente con `value`, `evidence`, `rule` y `"status": "answered"` |
| `review-export`: "stage 1 is not complete" | Corregir los errores de `check.json` y correr `check` |
| `run`: "approval files changed after the approval" | Algo cambió después de aprobar: `check` → `review-export` → el usuario aprueba de nuevo |
| `run`: "WRONG ACCOUNT" | El navegador tiene otra cuenta abierta: el usuario cambia de cuenta; nada se tocó |
| `run`: "STOPPED" con captura y `.aria.yaml` | La pantalla cambió: leer ambos, corregir `screens/<pantalla>.json`, `--dry-run`, y repetir |
| "The dedicated browser is not running" | `console.py open --profile <perfil>` |
| `play.py`: HTTP 404 en una edición | La app aún no tiene su primer AAB (pantalla `first_aab`) |

## Archivos

- `scripts/launch.py`, `scripts/console.py`, `templates/expediente.json`, `templates/review.html`, `rules/metadata.json`, `policies/sources.json`, `policies/snapshots/`, `screens/` (pantallas grabadas y `README.md`), `SETUP.md`. `accounts.json` (perfil → cuenta y puerto) y `last-tick.json` son por PC.
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
