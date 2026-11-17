---
name: app-promo-video
description: Crea y edita videos promocionales de apps móviles para TikTok, Reels, YouTube Shorts, YouTube y la ficha de Google Play (9:16 y 16:9, varios idiomas, variantes A/B de gancho), con grabaciones reales de la app hechas por Maestro, voz y música de ElevenLabs, escenas de IA de fal.ai para el gancho y composición en Remotion. Úsalo cuando pidan un "video promocional", "video para TikTok/YouTube/Play", "anuncio de la app", "promo", o cambiar uno ya hecho.
---

# Videos promocionales de apps

**Antes del primer uso en una PC o cuenta nueva: `SETUP.md`** (herramientas, teléfono, ElevenLabs, fal.ai, YouTube y Google Cloud, paso a paso).

Todo sale de un `video.json` por app. Los scripts graban, generan y renderizan; Claude decide, revisa con Read y pide aprobación. **Nunca grabar ni gastar antes de tener la aprobación del usuario.**

Ejemplo real (Bible Versions): `D:/Documents/BibleVersions/Images/promo-video/video.json`, flujos en `D:/Projects/Android/bible-versions/.maestro/promo/`, plan e historia en `plans/promo-video-skill-plan.md` de ese repo.

## Flujo (siempre en este orden)

1. **Detectar** (sin preguntar): repo y `app_id`; paleta y logo (`feature-graphic.json` del skill `play-feature-graphic`, o del código); funciones (pantalla de inicio, menú, strings, ficha de Play); flujos de Maestro existentes; claves (`PromoVideo-ElevenLabs`, `PromoVideo-Fal`); herramientas (ffmpeg, Node, Maestro, adb); teléfono (`adb devices`). Mostrar ✅/⚠️ y cómo resolver cada ⚠️.
2. **Preguntar solo lo que falta** (AskUserQuestion): formatos, idiomas, duración, número de ganchos, presupuesto (por defecto $20).
3. **Guion para aprobar** (`brief.md`): gancho(s) con texto y escena de IA, escenas con texto en pantalla y frase de la voz, y **costo estimado**. Toda afirmación (p. ej. "hasta 4 versiones") se verifica **en el código**, no en la ficha.
4. **Producir** por etapas, con pausas para aprobar (ver abajo).
5. **Entregar:** rutas, gasto real (`costs.json`), lista para publicar.

## Etapas de producción

| Etapa | Comando | Costo |
|---|---|---|
| Grabar escenas | `capture.py video.json [--scene a,b]` | $0 |
| Limpiar y hojas de contacto | `process_clips.py video.json [--scene a,b]` | $0 |
| Elegir tramos | Read de `recordings/<locale>/<escena>.sheet.jpg` → `in`/`out`/`rate` en `video.json` | $0 |
| Unir tramos de una grabación | `cut_clips.py video.json --locale <l> [--cut a,b]`: `capture.cuts.<locale>.<nombre> = {"from": escena, "ranges": [[ini,fin] o [ini,fin,velocidad]]}` → clip compacto `<nombre>.mp4` con su hoja; la escena usa `"clip": "<nombre>"`, `in` 0 y `out` = duración − 0,05 | $0 |
| Voz, música, whoosh | `audio.py video.json [--format] [--variant A]` | créditos ElevenLabs |
| Gancho: imagen temporal | `broll.py video.json --stage placeholder [--format] [--variant]` | ~$0,025 |
| Gancho: borrador | `broll.py ... --stage draft` | ~$0,12 c/u |
| Gancho: final | `broll.py ... --stage final`: el **borrador aprobado escalado a 1080p** (Topaz) y con los óvalos de `blur` | ~$0,04 c/u (`--regenerate`: Veo 3.1, ~$0,80) |
| Revisar un cuadro | `render.py video.json --still 6 [--format] [--variant]` | segundos |
| Vista previa | `render.py video.json [--format] [--variant]` → `...-preview.mp4` | ~2 s por segundo de video, 540p, solo con música |
| Final | `render.py video.json --final [--format] [--variant] [--voz]` | 1080p con música; `--voz` agrega la versión sin música `-voz.mp4` **solo si se pide explícitamente** |

**Velocidad:** `process_clips.py` deja de cada grabación una copia liviana (`<escena>.proxy.mp4`, 540 px, decodificación rápida); `--still` y las vistas previas la usan y solo `--final` lee las originales (~2× más rápido). Las vistas previas se llaman `-preview.mp4` para no pisar nunca un final aprobado. Un final de 79 s tarda ~20 min: lanzarlo en segundo plano.

Orden de aprobación: voz (muestras en `review/voces/`) → imágenes temporales (ajustar tiempos y textos con el propósito final a la vista) → borradores de IA → finales. `render.py --final` se niega mientras el gancho tenga imagen temporal o borrador.

## Reglas de calidad (aprendidas)

**Grabación**
- La app de Play no deja instalar la debug encima sin desinstalar (borra datos). Si hay que hacerlo, el usuario sincroniza con su nube y desinstala él; respaldar antes el APK de Play con `adb pull` de `pm path`.
- Navegar por la UI o con enlaces de debug; las pausas de Maestro se cortan solas (`freezedetect`). Cada grabación empieza con segundos de la escena anterior y **un instante de la pantalla de inicio del teléfono**: nunca usar esos segundos.
- **No hacer limpiezas** de ajustes que no afecten a otras grabaciones (p. ej. paneles). **Sí devolver y comprobar con assert** lo que cambia cómo se ven las demás (tamaño de letra, fuente, tema).
- Datos reales del usuario, nunca su correo ni datos personales en pantalla (p. ej. en Ajustes no bajar hasta la cuenta).
- Controles tipo joystick o gestos curvos: `"gesture"` en la escena (JSON para `gesture.py`), medir el centro del control en el código (márgenes en dp × densidad).
- **Pantallas que nunca se quedan quietas** (un reloj REC, una animación continua): Maestro espera segundos antes de cada toque (también con `waitToSettleTimeoutMs`) y el reloj marca minutos. Los toques van en un `"gesture"` con `"steps"` (`tap`, `swipe`, `wait_ms`: `adb input`, a ritmo natural), incluido el botón que arranca el reloj; el flujo solo deja la pantalla lista. Posiciones con `adb shell uiautomator dump` (los testTag de Compose salen como resource-id), en px del teléfono de la grabación (aprendido con Keyboard & Mouse, 2026-11-05).
- Lo que la app manda afuera (teclas a una PC, audio a otro equipo) no se ve en el teléfono: elegir escenas donde la app muestre la respuesta (globos de las teclas, contadores, barras de progreso). `show_touches` no sale en `screenrecord` en Samsung.
- `freeze_noise` por escena: cambios chicos (el globo de una tecla, un número) necesitan 0,0003-0,0005; con el valor por defecto la hoja marca 0 segmentos activos. Los tramos se eligen igual en la hoja (`in`/`out`/`rate`).
- Tamaño de pantalla forzado (`wm size`/`wm density` para grabar a 1080 px): respaldar y devolver al final, con assert. Si `capture.json` queda con `navigation_bar: 0` y la barra se ve en la hoja, corregirlo (el script ya usa la altura que declara el sistema cuando no encuentra la barra).
- Elementos dibujados dentro del texto o sin id (íconos, sliders): por posición, calibrada en una captura con cuadrícula.
- Seleccionar versículos que no arrastren títulos o números de capítulo; colores de resaltado que contrasten con el tema.
- Búsquedas: palabras que no sean parte de otras ("misericordia", no "amor" → "amorreo").
- **Otro idioma u otro teléfono** (aprendido 2026-11-04, Galaxy A21s con Android 12):
  - Sin idioma por app (`cmd locale` no existe): la app se pone en el idioma desde su pantalla de Idiomas (flujo `set_language.yaml`, `SEARCH=<nombre en inglés>`) y `capture.py --app-locale`.
  - Lo que va por posición depende del teléfono: `"gesture_by_model"` en la escena y ramas por teléfono en el flujo (Maestro no acepta un punto desde una variable: `runFlow when: true: ${PHONE === 'a21s'}`).
  - Revisar antes las preferencias que deja otra sesión en el teléfono: alcance de la búsqueda (otra Biblia u otro idioma), módulos de la vista paralela por idioma (`parallel_modules_<idioma>`), recientes. Respaldar antes de cambiarlas.
  - Un teléfono angosto ofrece menos paneles (A21s: 3); un idioma con una sola Biblia llena la paralela con comentarios (quitar la escena o cambiar el texto).
  - La lectura en voz alta necesita la voz de síntesis de ese idioma en el teléfono; si la app avisa que no hay, quitar la escena de audio.
  - Las grabaciones en un teléfono lento tardan más (la búsqueda puede girar 15 s): elegir los tramos en la hoja de contacto de cada idioma, no copiar los de otro.
  - Un bucle de bash en segundo plano sobrevive a TaskStop: guardar su PID y detenerlo antes de lanzar otra cola (dos Maestro a la vez en el mismo teléfono arruinan ambas).

**Edición**
- Gancho: escena de IA a pantalla completa con la pregunta encima; **sin pantallas de la app** en el gancho. El menú principal va al final ("Y mucho más") antes del cierre.
- Teléfono: entra inclinado con resorte y **termina recto**; durante la escena solo un zoom de 1,5 %.
- La pantalla del teléfono toma la proporción de cada grabación (`clipRatio`, de `<escena>.json`): un teléfono más alto la hace más angosta, nunca se recorta arriba ni abajo. La barra de estado limpia lleva detrás las primeras filas de la grabación estiradas, así una barra de color de la app (REC roja) llega hasta arriba como en el teléfono. Revisar siempre el borde superior en un still de cada escena.
- Subtítulos solo en escenas de funciones (en gancho y cierre repiten el texto grande o tapan el botón); ninguna palabra sola en un subtítulo.
- Vertical: textos dentro de las zonas seguras de TikTok (arriba 8 %, abajo 20 %, lado derecho). Horizontal: título y subtítulos a la izquierda, teléfono grande a la derecha.
- Cierre: logo (si es SVG con fondo, quitarlo; los huecos de letras pintados con el color de fondo se convierten en máscara), lema, botón de la tienda y, si el logo tiene partes, su animación (`logo_parts`). El nombre va en Cormorant por defecto; para apps técnicas o con marca sans, `"title_font": "sans"` (Inter 800).
- `keyword` se marca como frase (sus palabras seguidas): "teclado y mouse" no pinta el "¿Y" del principio.
- `palette` en `video.json` pisa la de `feature-graphic.json`: si el acento de la marca es oscuro (azul #2D5BFF sobre navy), usar uno más claro para que las palabras clave se lean.
- `--variant A` necesita `locales.<l>.hook_variants.A` y su audio (`audio.py --variant A`): sin eso el still falla o sale con otra duración.
- Cada escena dura lo que necesite su frase; el clip se ralentiza para cubrirla.

**Audio**
- Voz: muestras para elegir; frases con `previous_text`/`next_text` para que suene continua.
- **Cada idioma tiene su propia duración** (Forever Note: es 65 s, en 62 s): calcularla por idioma antes de `--only music`; la música se compone a la duración de cada uno y una diferencia de 1 s ya obliga a otra pista (~3000 créditos).
- **Antes de componer la música, ajustar la duración** (`render.build_props` + `promo_seconds`): los clips más largos que su frase alargan el video (Tracker dio 116 s). Acelerar con `rate` (una animación de ruta a ×2,8 se ve bien) o acortar `in`/`out`/frases; recién entonces `audio.py --only music`.
- Si los 3 intentos de música se apagan antes de tiempo, agregar al `prompt` "The groove stays full and driving right to the end, then lands on one big final hit with a short ring-out" (Tracker: OK al primer intento).
- El gancho por defecto toma la escena de IA de una variante con `"variant_broll": "B3"` en la escena hook.
- Música: compuesta a la **duración exacta** del video con final resuelto; `audio.py` comprueba que no se apague antes de tiempo (hasta 3 intentos). Todo a −14 LUFS.
- **Mezcla pareja** (`prepare_mix` en `render.py`, copias en `cache/mix/`; medido con Tracker, 2026-11-17). Música constante y suave en todo el video, que baja apenas cuando habla la voz:
  - **Música:** la compuesta crece sola de −21 a −11 LUFS (corto plazo) a lo largo del video. Se nivela con `dynaudnorm=f=250:g=15:m=12:p=0.9:r=0.12`, que la deja en −20 ±1 LUFS de principio a fin (con el final intacto), y se lleva a ~−17 LUFS (`MUSIC_LUFS`).
  - **Voz:** cada frase a −16 LUFS (`VOICE_LUFS`).
  - **Volúmenes:** música a 1,0 sin voz y a 0,6 mientras se habla (−4,4 dB, unos 5,5 dB bajo la voz), con rampas de 15 cuadros (`DUCK_RAMP`). Después, todo a −14 LUFS.
  - **No volver a 0,38 ni a 0,22:** con 0,22 (17 dB bajo la voz) la música "no se escucha" en los primeros 40 s, donde la voz habla casi sin pausa. Con la música sin nivelar y 0,38, la música tapaba la voz desde el segundo 40.
  - **Whoosh:** prompt "gentle low swoosh… warm and muted, no hiss, no click" (el "airy UI swipe" sonaba feo). Pasa por un filtro de 80 Hz a 7 kHz con bordes suaves, queda con pico a −6 dB y suena en volumen 0,3.
  - **Medir:** con `ebur128=metadata=1` (S = volumen de corto plazo); `volumedetect` engaña con intros de bajos.

**Costos y modelos**
- **Final = borrador aprobado escalado**, no otra generación (aprendido con Tracker, 2026-11-15): Veo 3.1 con el mismo prompt hizo otra escena ($0,80: sin el golpe, de atardecer, un resplandor como fuego, un logo legible); Topaz sobre el borrador mantuvo lo aprobado por $0,04. `--regenerate` solo si ningún borrador sirve.
- Para que un borrador salga realista: "genuine phone footage", tiempo real, ángulo de cámara explícito (p. ej. "from a second-floor window, high angle") y un `negative_prompt` propio con "slow motion, CGI, animation, stylized, exaggerated particles, low angle". La acción clave dentro del primer segundo y medio.
- La IA dibuja logos de marca y placas aunque el prompt los prohíba: revisar la parrilla y la placa en 1080p y taparlos con `"blur": [{x, y, rx, ry}]` en el gancho (óvalos suaves, px del final; ubicar en un cuadro con cuadrícula y comprobar 4-5 cuadros).
- Escenas de delito (robo de auto, ventana rota) pasan los filtros de flux y Veo Lite si no hay violencia contra personas y la cara queda en sombra.
- fal.ai cobra los videos sin audio como menos segundos (Veo 3.1 ×0,5, Lite ×0,6) y cada imagen como 1 megapíxel: `SILENT_FACTOR` en `broll.py`. La API de precios solo da el precio con audio.
- Los endpoints de Veo 3.1 en fal se anunciaron como retirados el 17-11-2026: si un modelo no tiene precio, proponer otro (Kling 3.0 Pro).
- Todo lo pagado va a `broll-library/` con caché por contenido (nunca por idioma): un idioma nuevo reutiliza escenas de IA y música.

## Publicar en YouTube (`publish.py`)

- Miniatura: por defecto el gancho a 1,8 s; con `publish.<locale>.thumbnail` (p. ej. la imagen destacada de Play) usa esa imagen entera en 1280×720 sobre una copia desenfocada de sí misma.
- `publish.py prepare video.json --locale <l> --format horizontal [--variant A]` → `upload/<nombre>/`: `video.mp4`, `thumbnail.jpg` (1280×720, el gancho), `captions-<lang>.srt` (de los tiempos de la voz), `title.txt`, `description.txt`, `tags.txt`, `metadata.json` y `CHECKLIST.md` con los pasos para subirlo a mano. Textos en `video.json` → `publish.<locale>`.
- `publish.py auth [<client_secret.json>] [--no-browser] [--profile <nombre>]` (una vez por cuenta): OAuth de escritorio con PKCE; guarda `PromoVideo-YouTube-Client[@perfil]` y `PromoVideo-YouTube[@perfil]`. Sin el JSON reutiliza el cliente guardado (para volver a autorizar si el token venció). El usuario usa contenedores de Firefox: siempre `--no-browser` y pasarle el enlace. **Varias cuentas de Google:** un proyecto de Google Cloud y un perfil por cuenta; cada app elige el suyo con `"youtube_profile"` en `video.json` (ver SETUP.md 6.4). ElevenLabs y fal.ai son compartidos.
- `publish.py check [--profile <nombre>]`: renueva el token y lee el canal, sin subir nada. Correrlo antes de `upload`; con `invalid_grant`, ver SETUP.md 6.2.6 y 6.3.
- `publish.py upload ... [--privacy unlisted]`: videos.insert + miniatura + subtítulos, con `embeddable`, `selfDeclaredMadeForKids: false` y `containsSyntheticMedia: true`. Lee la privacidad real: los proyectos de API **sin auditoría** quedan forzados a privado (documentación oficial); entonces se cambia en Studio si se puede, o se sube a mano con el CHECKLIST. Guarda el id y el enlace en `video.json` (`publish.<locale>.uploaded`), así nunca sube dos veces.
- Pantalla de consentimiento en modo **Prueba**: el token de actualización caduca a los 7 días (hay que repetir `auth`). Para que no caduque, llenar el Branding y publicar la app (SETUP.md 6.2.4 y 6.2.6). El aviso "Your app requires verification" se ignora: no enviarla a revisión, la app sin verificar basta para el canal propio (al autorizar aparece "app no verificada" y se acepta).
- Nunca automatizar YouTube Studio con Playwright o similares: va contra los términos de YouTube.

## Publicar (decirlo siempre al entregar)

- **TikTok:** etiqueta "Contenido generado por IA" (escenas con personas). La versión sin música (`-voz.mp4`) no se genera por defecto: solo con `--voz` cuando el usuario la pida explícitamente (p. ej. para elegir canción de la biblioteca comercial de TikTok).
- **YouTube / Google Play:** horizontal con música; público u oculto, **sin monetización**, inserción permitida, "contenido alterado o sintético: sí"; pegar en Play Console el enlace sin parámetros. Play abre YouTube y se ve completo.

## Claves

Administrador de credenciales de Windows (genérica, usuario `api`), con la línea de `Read-Host` (nunca pegar la clave en el chat ni en un comando):
`PromoVideo-ElevenLabs` (permisos: texto a voz, música, efectos, voces lectura, modelos, usuario) y `PromoVideo-Fal`. En otros sistemas: `ELEVENLABS_API_KEY`, `FAL_KEY`.

## Archivos

- `scripts/`: `common.py`, `capture.py`, `gesture.py`, `process_clips.py`, `cut_clips.py`, `audio.py`, `broll.py`, `render.py`, `qa.py`, `publish.py`.
- `remotion/`: proyecto (Remotion 4.0.529); `src/scenes/` (Hook, Feature, Outro), `src/components/` (Phone, StatusBar, KineticText, Captions, Soundtrack, Background).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
