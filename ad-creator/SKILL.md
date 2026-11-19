---
name: ad-creator
description: Crea el anuncio intersticial web (custom_web) de una app Android a partir de su video promocional vertical (skill app-promo-video) - una página HTML liviana con el mismo gancho de IA, las mismas frases con su palabra clave, cuadros reales de las grabaciones dentro de un teléfono que entra inclinado, el cierre con el logo animado y la insignia de Google Play, en inglés y español - lista para la WebView a pantalla completa de la librería de anuncios propios (?lang, #ctaButton, botón de cerrar arriba a la derecha, 5 s obligatorios). Si la app no tiene video, primero hace las etapas gratis de app-promo-video (guion, grabaciones, imagen del gancho). Úsalo cuando pidan "crear un anuncio", "ad para la app", "anuncio intersticial", "anuncio web", "custom ad", "ad-creator" o "un anuncio como el del video".
---

# Anuncios web desde el video promocional

El anuncio es el video vertical de `app-promo-video` hecho página: mismas escenas, mismos textos, mismas
grabaciones, con animaciones CSS en vez de video (pesa ~550 KB, carga ~70 KB antes de mostrarse). Formato y
contrato con la app: `references/format.md` (leerlo antes de cambiar la plantilla).

Todo pasa por `scripts/ad.py` (con `python`; necesita ffmpeg, Pillow y Playwright con Edge):

| Comando | Qué hace |
|---|---|
| `config --ads-root <carpeta>` | Una vez por PC: dónde se escriben los anuncios (`<carpeta>/<guid>/index.html` + `img/`). **Preguntarle al usuario** la carpeta (la de anuncios de su servidor); se guarda en `config.json` del skill (no va al respaldo) |
| `init <promo-video/video.json> [--guid] [--features 6]` | Escribe `<carpeta de la app>/ad/ad.json` desde el video: idiomas, gancho, hasta 6 funciones con sus textos y 3 momentos de cada grabación, cierre, colores, ícono, logo, enlace de Play. GUID nuevo si no se da (el del anuncio que la app ya pide, si se rehace uno) |
| `build <ad.json>` | Saca los cuadros (ffmpeg), el gancho, el ícono, el logo y las insignias en WebP con nombres con hash, y genera `index.html` desde `templates/index.html`. Avisa textos largos, palabras clave que no están en su texto y si gancho + primera función no cubren los 5 s |
| `qa <ad.json> [--sizes 360x780,412x915]` | Capturas de cada escena congelada (`?t=`) por idioma y tamaño y una hoja por idioma en `<app>/ad/qa/`; comprueba errores de JS, imágenes que fallan y el enlace de `#ctaButton` |
| `serve <ad.json>` | Vista previa local |

`ad.json` es la fuente (textos, escenas, segundos de cada cuadro, colores); `index.html` se genera: nunca se edita a mano.

## Flujo

1. **Buscar el video** (sin preguntar): `<carpeta de la app>/promo-video/video.json` o `Images/promo-video/video.json`
   (`D:/Documents/Apps/<App>/`). Mirar sus escenas verticales y, si existe, el video final (`output/promo-<locale>-vertical*.mp4`)
   o una hoja de contacto, para entender la idea.
2. **Si no hay video**, generarlo desde cero con `app-promo-video` **solo hasta lo necesario para el anuncio** (con sus reglas y
   aprobaciones): guion (`brief.md`, aprobado por el usuario), grabaciones (`capture.py`), limpieza y tramos
   (`process_clips.py`, `in`/`out`), y la escena de IA del gancho (`broll.py --stage placeholder`, ~$0,025; un borrador
   si el usuario lo aprueba). Sin voz, música ni render. Luego seguir aquí.
3. `ad.py config` si es la primera vez en la PC; `ad.py init`.
4. **Revisar `ad.json`** (Claude, sin preguntar lo que se puede decidir):
   - Funciones: las 6 más fuertes y que se entiendan **sin sonido**; la primera es la que se ve en los 5 s obligatorios.
     Quitar las que dependen de la voz (p. ej. dos escenas seguidas de exportar/importar) o reescribir su título.
   - Textos: gancho ≤ 60 caracteres, funciones ≤ 34; la palabra clave tal cual dentro del texto; mismo sentido en cada idioma.
   - `times` de cada función: 3 segundos dentro del tramo de la grabación; mover los que caen en una transición,
     un teclado que tapa todo, una pantalla de carga o datos personales. `tap` opcional donde el segundo cuadro
     responde a un toque.
   - Colores (`colors`, derivados de la paleta del video), ícono y logo (`logo.parts` si el logo tiene partes animables).
5. `ad.py build` → `ad.py qa` → **revisar las hojas con Read**: textos que se cortan, esquina superior derecha vacía,
   cuadros del idioma correcto, el teléfono sin tapar la insignia, el cierre completo. Corregir `ad.json` y repetir.
6. Entregar: la ruta de `<guid>/index.html`, el GUID (es el que se configura en la app o en el servidor de anuncios),
   las hojas de QA y el peso. Publicar el servidor o hacer commit **solo si el usuario lo pide**.

## Reglas

- El anuncio sigue el formato del video: gancho de IA a pantalla completa con la pregunta, sin pantallas de la app en el
  gancho; funciones con el teléfono que entra inclinado y termina recto; cierre con logo, lema e insignia.
- Solo cuadros reales de la app (de las grabaciones), nunca pantallas inventadas ni maquetas dibujadas en HTML.
- Nunca datos personales en un cuadro (correo, cuenta, notificaciones).
- Las imágenes cambian de nombre cuando cambian (el servidor las guarda un año en caché): no renombrar a mano.
- Inglés y español (lo único que la app envía en `?lang`); otro idioma del video se incluye pero la app no lo pedirá.
- Un anuncio existente se rehace con el mismo GUID (`init --guid <el de siempre> --force`, o editar su `ad.json`).
- El skill no conoce ningún servidor ni sitio concreto: la carpeta de salida sale de `config.json` (por PC).

## Archivos

- `scripts/ad.py`, `templates/index.html` (la página, con la configuración inyectada por `build`),
  `assets/google-play-badge-{en,es}.png` (insignias oficiales), `references/format.md` (contrato y diseño).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo
  ahí (sin `config.json`); no hacer copias en otros lugares.
