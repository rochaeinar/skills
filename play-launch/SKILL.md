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

## Etapa 3 es autónoma (no preguntar)

Con la aprobación válida y la sesión iniciada, Claude **ejecuta todo de corrido sin pedir confirmaciones**: crear la app, firma, primer AAB, declaraciones, ficha, prueba cerrada y envío a revisión. Lo aprobado ya es la autorización. Solo se detiene si (a) falta algo que solo el usuario puede dar (contraseña, archivo personal), (b) una pantalla pide algo que no está en lo aprobado o contradice la evidencia, o (c) una acción afectaría a otras apps o a la cuenta (p. ej. políticas de Google Cloud). Si un camino falla (p. ej. la API sin permiso), usa otro (la consola) sin preguntar. Al final, un solo informe con lo hecho, la evidencia y lo pendiente. Producción sigue necesitando confirmación o preaprobación (día 14).

## Guiar al usuario (Claude lleva el proceso, no el usuario)

- **Claude corre todos los comandos** (abrir el navegador dedicado, `whoami`, `next`, pantallas, API). Al usuario solo se le piden acciones físicas o personales: iniciar sesión, escribir una contraseña, subir un archivo a su Drive, aprobar. Una a la vez, con el paso exacto (qué abrir, qué botón, qué pegar dónde) y qué decir al terminar.
- **Antes de cada acción importante o sin vuelta atrás** (crear la app, la clave de firma, enviar a revisión, pedir producción) explicar en 2-3 líneas qué va a pasar y qué queda fijo (p. ej. "el paquete queda registrado para siempre; el certificado se fija en el paso siguiente, no aquí"), sobre todo si la pantalla muestra algo nuevo (recuadros, avisos, opciones por defecto). Nunca pasar por encima de un recuadro o aviso de la consola sin leerlo y contarlo.
- Cada decisión pendiente va con la opción recomendada y su porqué; si el usuario no contesta, seguir con lo que no depende de ella.
- El usuario nunca debería tener que preguntar "¿y ahora qué?" o "¿dónde?": si lo pregunta, la respuesta anterior estuvo incompleta.

## Informar al usuario (siempre, al terminar cualquier paso)

El usuario no sabe en qué etapa está ni dónde mirar si no se lo dicen. **Cada respuesta que cierra un paso termina con `launch.py next`** (o su contenido) en palabras simples:

1. **En qué etapa está cada app** (1 generar · 2 tu revisión · 3 ejecución · 4 prueba y producción).
2. **Dónde revisar**: el enlace de la página de revisión (`state.json` → `review_url`), las rutas exactas de los archivos que tiene que mirar o subir.
3. **Qué tiene que hacer él**, en pasos numerados y concretos (qué botón, qué decirle a Claude al terminar).
4. **Qué falta y quién lo resuelve** (Claude o él), incluidos los pendientes que bloquean la aprobación.
5. Las decisiones que se le piden, una por una.

Nunca terminar con "falta la etapa 2" sin el enlace y los pasos. La revisión puede empezar con hasta 3 pendientes (`MAX_PENDING_FOR_REVIEW`): la página los muestra en rojo y no deja aprobar hasta resolverlos.

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
6. **Capturas de la tienda (regla del usuario):** siempre con la **resolución que captura el teléfono**, sin escalar ni recortar el contenido. Solo se quitan la barra de estado (hora, batería) y la de navegación, y se completa el ancho con el color de fondo de la app lo mínimo para no pasar de 2:1. **No** se rehacen en 9:16 aunque la consola escriba "16:9 o 9:16": la consola acepta hasta 2:1 (probado el 2026-11-15). Con un teléfono de 720 px no califican para la promoción de Play (pide 1080 px por lado); eso se acepta.
   **Recursos** (skills existentes): capturas por idioma con Maestro en `play/images/<lang>/phoneScreenshots/` (y tablets 7"/10"), ícono 512 y `featureGraphic.png` (`play-feature-graphic`), video promocional (`app-promo-video`, el gasto se aprueba en la revisión), **video de cada servicio en primer plano** (flujo Maestro del uso real + `screenrecord`, subido oculto; el enlace va en `expediente.videos.fgs_<tipo>`).
7. **Seguridad de los datos**: el CSV con los ids de Play (`launch/data-safety.csv`). La plantilla se exporta una vez desde Play Console (*App content > Data safety > Export to CSV*) y se guarda en `templates/data-safety-template.csv`; Claude la llena desde el análisis.
8. `launch.py check --app <carpeta>`: límites de caracteres, palabras prohibidas por la política de metadatos, tamaños de imágenes, declaraciones con evidencia y regla, coherencia (anuncios y analítica del build contra lo declarado, video y texto por servicio en primer plano, `targetSdk` mínimo, CSV, AAB, contacto), y que la política de privacidad responda. **Sin errores** pasa a `generated`.

## Etapa 2: revisión del usuario

1. `launch.py review-export --app <carpeta> [--app ...] --out <scratchpad>/review`: datos de la página (un documento por texto, imagen, video, declaración y la configuración), las imágenes y los pendientes de `check.json` (hasta 3; se ven en rojo y bloquean la aprobación).
2. Copiar `templates/review.html` a esa carpeta y publicarlo con la herramienta Artifact (la primera vez con `icon: "checklist"`), `files` = el mapa de `files.json`, `capabilities: {db: {}, user: {}}`. Después, cargar los datos con `ArtifactData` `batch` por cada lista de `batches.json` (escrituras `set` con `file_path`, rutas con `/`), y una lectura `list` de `apps` para comprobar. Una sola página sirve para todas las apps del lote: actualizarla publicando el mismo archivo.
3. `launch.py review-published <url> --app <carpeta> [--app ...]`: guarda el enlace en cada app e imprime el mensaje para el usuario. Dárselo tal cual (ver "Informar al usuario"). En la página ve **los textos primero**, editables, con su conteo y el idioma base al lado; marca cada texto como revisado, deja notas y aprueba por app o todas.
   - **Lo que solo el usuario puede dar** (enlace del video de una declaración, correo de contacto...) va como **campo en la sección "Lo que falta de ti"**, arriba de todo, con los pasos en español para conseguirlo (`user_inputs` en `launch.py`; agregar ahí cada caso nuevo). Nunca pedirlo solo en el chat ni dejarlo como un error técnico en rojo: el usuario tiene que poder pegarlo en la página. La aprobación queda bloqueada hasta que el campo sea válido.
   - **Actualizar una página ya publicada sin pisar al usuario**: nunca volver a escribir con `set` los documentos que ya existen (borraría sus ediciones y sus "Revisado"). Exportar a otra carpeta y escribir solo los documentos nuevos (`set`) y los cambios puntuales (`update` con `if_version`, p. ej. `pending` de `apps`); la plantilla se republica con el mismo archivo.
4. `ArtifactData list` de `items`, `apps` y `approvals` con `out_dir=<scratchpad>/review-in`, y `launch.py review-import --from <scratchpad>/review-in`: aplica los textos editados a sus archivos, guarda las notas en `review-notes.md` y registra la aprobación con el hash de todos los archivos. **Con notas no se registra la aprobación**: Claude las aplica, vuelve a correr `check` y `review-export`, y el usuario aprueba de nuevo.
5. `launch.py approval`: la aprobación vale mientras ningún archivo cambie. Cualquier cambio posterior la anula.

## Etapa 3: ejecución (después de que el usuario inicia sesión)

1. El usuario: `console.py open --profile <perfil>` e inicia sesión a mano (la primera vez además `console.py bind --profile <perfil>`). Avisa a Claude.
2. Claude: `launch.py approval` y `console.py whoami --profile <perfil>`. Si la cuenta no es la vinculada, se detiene.
3. **Firma (antes de todo lo demás después de crear la app): leer `references/firma-en-play.md`.** Play inscribe las apps nuevas en firma híbrida con claves de Google; hay que cambiarla a la clave propia (PEPK) antes del primer AAB, comprobar que las huellas de la página coinciden con `app.json` y, con el primer AAB procesado, correr `launch.py verify-signing --version-code N`. El recuadro de "protección automática" de *Crear app* no cambia el certificado. Antes de crear la app, explicarle al usuario en dos líneas qué certificado quedará y dónde se fija.
4. Pantallas sin API, en este orden, cada una con `console.py run <pantalla> --app <carpeta>` (ver `screens/README.md`; una pantalla en `draft` se graba y se prueba con `--dry-run` primero): `create_app` → `bind-app` → `app_signing` (PEPK con la clave de `app-init`) → `first_aab` → `privacy_policy`, `app_access`, `ads`, `advertising_id`, `content_rating`, `target_audience`, `foreground_services`, `other_declarations`, `category`, `countries`.
5. Por API: `play.py details --email … --website … --yes`, `play.py data-safety <csv> --yes`, `play.py push-listing --yes`, `play.py testers --track alpha --groups <grupo> --yes`, `play.py release <aab> --track alpha --yes`.
6. `send_for_review` (pantalla) y `launch.py set-state closed-test`. Mensaje a los testers: `launch/texts/tester-message.txt` con el enlace de inscripción (el usuario lo envía).
7. Verificación: cada pantalla relee lo guardado (`readback`) y deja captura en `evidence/<fecha>/`. Al final, informe al usuario con las capturas y lo que quedó pendiente.

## Después: prueba cerrada, producción, revisión

- `launch.py tick` (diario, Programador de tareas; ver SETUP.md): consulta el estado de revisión por API, cuenta los días de la prueba cerrada y avisa lo que necesita al usuario. Nunca toca pantallas.
- Día 14: Claude lee el conteo de inscritos (`closed_test_count`), redacta las respuestas de la solicitud de producción a partir de la prueba real (comentarios de los testers, versiones subidas) en `launch/texts/production-answers.txt`, y con la aprobación (o la preaprobación con criterios) corre `production_request`.
- Aprobada: `play.py promote --from alpha --to production --rollout <production_rollout> --yes`, luego subir al 100 % (`android-release`).
- `launch.py status`: todas las apps y su estado. `launch.py next`: lo mismo en palabras para el usuario (dónde revisar, qué hacer, qué falta).

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
