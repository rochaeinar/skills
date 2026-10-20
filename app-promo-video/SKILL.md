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
| Voz, música, whoosh | `audio.py video.json [--format] [--variant A]` | créditos ElevenLabs |
| Gancho: imagen temporal | `broll.py video.json --stage placeholder [--format] [--variant]` | ~$0,025 |
| Gancho: borrador | `broll.py ... --stage draft` | ~$0,12 c/u |
| Gancho: final | `broll.py ... --stage final` | ~$0,80 c/u |
| Revisar un cuadro | `render.py video.json --still 6 [--format] [--variant]` | segundos |
| Vista previa | `render.py video.json [--format] [--variant]` → `...-preview.mp4` | ~2 s por segundo de video, 540p, solo con música |
| Final | `render.py video.json --final [--format] [--variant]` | 1080p + versión `-voz` |

**Velocidad:** `process_clips.py` deja de cada grabación una copia liviana (`<escena>.proxy.mp4`, 540 px, decodificación rápida); `--still` y las vistas previas la usan y solo `--final` lee las originales (~2× más rápido). Las vistas previas se llaman `-preview.mp4` para no pisar nunca un final aprobado. Un final de 79 s tarda ~20 min: lanzarlo en segundo plano.

Orden de aprobación: voz (muestras en `review/voces/`) → imágenes temporales (ajustar tiempos y textos con el propósito final a la vista) → borradores de IA → finales. `render.py --final` se niega mientras el gancho tenga imagen temporal o borrador.

## Reglas de calidad (aprendidas)

**Grabación**
- La app de Play no deja instalar la debug encima sin desinstalar (borra datos). Si hay que hacerlo, el usuario sincroniza con su nube y desinstala él; respaldar antes el APK de Play con `adb pull` de `pm path`.
- Navegar por la UI o con enlaces de debug; las pausas de Maestro se cortan solas (`freezedetect`). Cada grabación empieza con segundos de la escena anterior y **un instante de la pantalla de inicio del teléfono**: nunca usar esos segundos.
- **No hacer limpiezas** de ajustes que no afecten a otras grabaciones (p. ej. paneles). **Sí devolver y comprobar con assert** lo que cambia cómo se ven las demás (tamaño de letra, fuente, tema).
- Datos reales del usuario, nunca su correo ni datos personales en pantalla (p. ej. en Ajustes no bajar hasta la cuenta).
- Controles tipo joystick o gestos curvos: `"gesture"` en la escena (JSON para `gesture.py`), medir el centro del control en el código (márgenes en dp × densidad).
- Elementos dibujados dentro del texto o sin id (íconos, sliders): por posición, calibrada en una captura con cuadrícula.
- Seleccionar versículos que no arrastren títulos o números de capítulo; colores de resaltado que contrasten con el tema.
- Búsquedas: palabras que no sean parte de otras ("misericordia", no "amor" → "amorreo").

**Edición**
- Gancho: escena de IA a pantalla completa con la pregunta encima; **sin pantallas de la app** en el gancho. El menú principal va al final ("Y mucho más") antes del cierre.
- Teléfono: entra inclinado con resorte y **termina recto**; durante la escena solo un zoom de 1,5 %.
- Subtítulos solo en escenas de funciones (en gancho y cierre repiten el texto grande o tapan el botón); ninguna palabra sola en un subtítulo.
- Vertical: textos dentro de las zonas seguras de TikTok (arriba 8 %, abajo 20 %, lado derecho). Horizontal: título y subtítulos a la izquierda, teléfono grande a la derecha.
- Cierre: logo (si es SVG con fondo, quitarlo; los huecos de letras pintados con el color de fondo se convierten en máscara), lema, botón de la tienda y, si el logo tiene partes, su animación (`logo_parts`).
- Cada escena dura lo que necesite su frase; el clip se ralentiza para cubrirla.

**Audio**
- Voz: muestras para elegir; frases con `previous_text`/`next_text` para que suene continua.
- Música: compuesta a la **duración exacta** del video con final resuelto; `audio.py` comprueba que no se apague antes de tiempo (hasta 3 intentos). Baja a ~38 % mientras habla la voz. Todo a −14 LUFS.
- Licencia ElevenLabs Music: desde Starter, uso comercial online sin atribución (verificado 2026-10-18 en elevenlabs.io/music-terms). Generar solo con plan de pago activo.

**Costos y modelos**
- fal.ai cobra los videos sin audio como menos segundos (Veo 3.1 ×0,5, Lite ×0,6) y cada imagen como 1 megapíxel: `SILENT_FACTOR` en `broll.py`. La API de precios solo da el precio con audio.
- Los endpoints de Veo 3.1 en fal se anunciaron como retirados el 17-11-2026: si un modelo no tiene precio, proponer otro (Kling 3.0 Pro).
- Todo lo pagado va a `broll-library/` con caché por contenido (nunca por idioma): un idioma nuevo reutiliza escenas de IA y música.

## Publicar en YouTube (`publish.py`)

- `publish.py prepare video.json --locale <l> --format horizontal [--variant A]` → `upload/<nombre>/`: `video.mp4`, `thumbnail.jpg` (1280×720, el gancho), `captions-<lang>.srt` (de los tiempos de la voz), `title.txt`, `description.txt`, `tags.txt`, `metadata.json` y `CHECKLIST.md` con los pasos para subirlo a mano. Textos en `video.json` → `publish.<locale>`.
- `publish.py auth <client_secret.json> [--no-browser] [--profile <nombre>]` (una vez por cuenta): OAuth de escritorio con PKCE; guarda `PromoVideo-YouTube-Client[@perfil]` y `PromoVideo-YouTube[@perfil]`. **Varias cuentas de Google:** un proyecto de Google Cloud y un perfil por cuenta; cada app elige el suyo con `"youtube_profile"` en `video.json` (ver SETUP.md 6.4). ElevenLabs y fal.ai son compartidos.
- `publish.py upload ... [--privacy unlisted]`: videos.insert + miniatura + subtítulos, con `embeddable`, `selfDeclaredMadeForKids: false` y `containsSyntheticMedia: true`. Lee la privacidad real: los proyectos de API **sin auditoría** quedan forzados a privado (documentación oficial); entonces se cambia en Studio si se puede, o se sube a mano con el CHECKLIST. Guarda el id y el enlace en `video.json` (`publish.<locale>.uploaded`), así nunca sube dos veces.
- Pantalla de consentimiento en modo **Prueba**: el token de actualización caduca a los 7 días (hay que repetir `auth`). Para que no caduque, publicar la app (aparece el aviso de "app no verificada" al autorizar, que se acepta) o pasar la verificación.
- Nunca automatizar YouTube Studio con Playwright o similares: va contra los términos de YouTube.

## Publicar (decirlo siempre al entregar)

- **TikTok:** etiqueta "Contenido generado por IA" (escenas con personas). `-voz.mp4` si se elige canción de la biblioteca comercial de TikTok.
- **YouTube / Google Play:** horizontal con música; público u oculto, **sin monetización**, inserción permitida, "contenido alterado o sintético: sí"; pegar en Play Console el enlace sin parámetros. Play abre YouTube y se ve completo.

## Claves

Administrador de credenciales de Windows (genérica, usuario `api`), con la línea de `Read-Host` (nunca pegar la clave en el chat ni en un comando):
`PromoVideo-ElevenLabs` (permisos: texto a voz, música, efectos, voces lectura, modelos, usuario) y `PromoVideo-Fal`. En otros sistemas: `ELEVENLABS_API_KEY`, `FAL_KEY`.

## Archivos

- `scripts/`: `common.py`, `capture.py`, `gesture.py`, `process_clips.py`, `audio.py`, `broll.py`, `render.py`, `qa.py`, `publish.py`.
- `remotion/`: proyecto (Remotion 4.0.529); `src/scenes/` (Hook, Feature, Outro), `src/components/` (Phone, StatusBar, KineticText, Captions, Soundtrack, Background).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
