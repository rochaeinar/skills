# Formato del anuncio (custom_web)

Todo lo que el anuncio debe cumplir, aprendido con el primer anuncio hecho a mano desde un video promocional
(noviembre de 2026). La plantilla `templates/index.html` ya lo cumple: esto explica por qué, para no romperlo al cambiarla.

## Dónde se muestra

- Una **WebView a pantalla completa** de la librería de anuncios propios de la app (`com.erc.customads`, proveedor
  `custom_web`, `AdActivity`). La URL es `https://<servidor>/ads/<guid>/index.html`; la app agrega `?lang=es|en`
  (solo esos dos: cualquier otro idioma del dispositivo llega como `en`).
- La WebView se **precarga oculta** (espera `onPageFinished`) y se muestra después. Por eso:
  - el reloj del anuncio arranca con el primer `requestAnimationFrame` (rAF no corre mientras está oculta) y
    **reinicia desde el gancho** cuando vuelve a verse (`visibilitychange`, o un salto de más de 1 s entre cuadros);
  - lo que retrasa `onPageFinished` es solo el gancho, el ícono, la insignia y la primera función; el resto de las
    imágenes se pide cuando el anuncio ya está en pantalla. Un `img` con `src` cuenta para la carga; `data-src` no.
- El **botón nativo de cerrar** está arriba a la derecha: esa esquina queda vacía (la marca va arriba a la izquierda).
- Solo los **primeros 5 s son obligatorios** (luego se puede cerrar): el gancho (3,4 s) y la primera función deben
  caber, y la primera función es la más fuerte.
- **Clic**: la app intercepta la navegación de la WebView (`shouldOverrideUrlLoading` → abre Play y registra el clic).
  El enlace es `#ctaButton` (`href` = la ficha de Play; `?cta=<url>` lo cambia). Un toque en cualquier parte hace
  `cta.click()`, salvo en los primeros 0,6 s en pantalla (un toque dirigido a la app no cuenta como clic).

## Escenas (las del video vertical)

| Escena | Dura | Qué hace |
|---|---|---|
| Gancho | 3,4 s | la escena de IA del video a pantalla completa con un acercamiento lento (`kb`), degradado oscuro arriba y abajo, la pregunta arriba palabra por palabra con la palabra clave en el color de acento |
| Función (hasta 6) | 3,2 s la primera, 2,8 s el resto | título arriba (palabra por palabra, palabra clave en acento); el teléfono entra inclinado con resorte (`enter`: −7°, 90 %, desde abajo) y termina recto con un zoom de 1,5 % (`drift`); dentro, 2-3 cuadros reales de la grabación que se funden como un clip corto (a 0, 0,95 y 1,85 s) |
| Cierre | 3,6 s | el logo crece (`grow`); si tiene partes, la primera se asienta (`settle`) y las demás entran nadando (`swim`, 1,1 s después); nombre (si el logo no lo incluye), lema, «Gratis en Google Play» y la insignia grande que late (`bump`); la insignia chica de abajo se oculta |

- Siempre visibles: arriba a la izquierda ícono + nombre + etiqueta «Anuncio»/«Ad»; abajo la insignia de Google Play
  y los puntos de progreso (uno por función).
- Una escena cuya imagen todavía no llegó (red lenta) **se salta**, nunca se muestra vacía; un cuadro que no llegó
  deja el anterior.
- Toque opcional (`tap` en la escena: `{"es": [x, y]}`, fracción de la pantalla): un círculo que marca dónde se toca,
  a los 0,45 s; útil cuando el segundo cuadro es la respuesta a un toque.
- `prefers-reduced-motion`: sin animaciones, todo visible.
- Bucle de ~24 s; vuelve a empezar.

## Textos

- Los mismos del video (`text` y `keyword` de cada escena del `video.json`, por idioma). La palabra clave tiene que
  aparecer tal cual en el texto. La puntuación pegada a la palabra clave («contexto?») no se separa de su línea.
- Gancho ≤ 60 caracteres; función ≤ 34 (dos líneas como máximo a 360 px). Si el texto del video es más largo,
  acortarlo en `ad.json`, no en el video.
- Si una función del video necesita la voz para entenderse (p. ej. «Exporta en tu PC» sin decir de dónde), elegir
  otra o reescribir el título para que se entienda solo: el anuncio no tiene sonido.

## Imágenes

- Cuadros de la grabación limpia del video (`recordings/<locale>/<clip>.mp4`, sin barras de estado ni navegación),
  dentro del tramo que usa el video (`in`/`out`), 360 px de ancho, WebP 80. Revisar que cada cuadro muestre la
  acción (no una transición, un teclado tapando todo o datos personales).
- Gancho: un cuadro de la escena de IA final (`broll/vertical.json`: `final`, si no `draft` o `placeholder`) en el
  segundo de la acción clave (1,8 s), recortado a 540×960.
- Ícono 192 px, logo SVG tal cual o WebP 400 px, insignias oficiales de Google Play recortadas a 480 px de ancho.
- **El servidor guarda `img/` en caché un año** (immutable): una imagen que cambia necesita otro nombre. `build`
  pone el hash del contenido en cada nombre y borra las que ya no se usan.
- Peso orientativo: ~550 KB en total, ~70 KB antes de mostrarse.

## Vista previa

- `?t=<segundos>` congela el anuncio en ese momento (animaciones incluidas): es lo que usa `qa`.
- `?lang=es|en`.
