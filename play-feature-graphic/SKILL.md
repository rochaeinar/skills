---
name: play-feature-graphic
description: Genera la imagen destacada (feature graphic) de Google Play, 1024x500 PNG, para cualquier app y en varios idiomas, a partir de capturas reales, el logo, la paleta de colores y las funciones más importantes sacadas del código. Úsalo cuando pidan "feature graphic", "imagen destacada", "gráfico de funciones", "banner de Play Store", "imagen principal de la ficha" o versiones localizadas de ella.
---

# Feature graphic de Google Play

Requisitos de la PC: `SETUP.md`.

Produce una imagen elegante y llamativa: a la izquierda el logo, el nombre de la app, un lema corto y 3 etiquetas de funciones (la principal resaltada); a la derecha tres teléfonos con capturas reales (el del centro al frente y los laterales inclinados ±7°), sobre el fondo oscuro de la app con un brillo suave del color de marca.

Todo lo hace `scripts/build_feature_graphic.py` a partir de un `config.json`: recorta las capturas, aísla el logo, rellena `templates/feature.html`, lo renderiza con Edge o Chrome headless y guarda un PNG de 24 bits sin alfa, de 1024x500 exactos.

Ejemplo real (Bible Versions): `D:/Documents/BibleVersions/Images/feature-graphic/feature-graphic.json`.

## Requisitos de Google Play

- PNG o JPEG, **1024 x 500 px exactos**, hasta 15 MB. PNG de 24 bits, **sin canal alfa** (el script lo convierte a RGB).
- Se sube una por idioma de la ficha (Play Console > Presencia en Play Store > Ficha principal > Gráficos, para cada traducción).
- Si la ficha tiene video, Play pone el botón de reproducir **en el centro**: nada importante ahí.
- Mantener texto y logo lejos de los bordes (Play puede recortar o redondear).
- Prohibido: rankings, premios, "gratis", "descarga ya", precios, insignias de tiendas, texto engañoso. Solo el nombre, un lema y funciones.
- Texto poco y grande: en el teléfono la imagen se ve a ~360 px de ancho. El título debe leerse a ese tamaño.

## Flujo de trabajo

### 1. Reunir la información del código

| Dato | Android | iOS / Flutter / web |
|---|---|---|
| Nombre | `res/values*/strings.xml` > `app_name` | `Info.plist` `CFBundleDisplayName`, `pubspec.yaml`, `manifest.json` |
| Logo | `app/src/main/ic_launcher-playstore.png` (512x512), o `res/mipmap-xxxhdpi/ic_launcher_foreground.png` | `Assets.xcassets/AppIcon`, `assets/icon`, `public/icon-512.png` |
| Paleta | `res/values-night/colors.xml` y `values/colors.xml`, `themes.xml` (`colorPrimary`, `colorSecondary`, fondos) | `Color` assets, `ThemeData`, variables CSS o `tailwind.config` |
| Funciones | pantalla de inicio (tarjetas o accesos), menú, `strings.xml`, notas de versión, ficha actual de Play | igual |

- **Paleta:** `bg` = fondo oscuro de la app (si solo tiene tema claro, usar el tono de marca más oscuro); `accent` = el color más vivo de la marca (a menudo el del logo: lee el píxel con PIL); `accent_soft` = acento suavizado de la UI; `deep` = verde/azul oscuro de marca para el brillo de esquina. Comprobar contraste: el texto del chip resaltado (`on_accent`) sobre `accent` debe ser ≥ 4.5:1.
- **Logo:** si el ícono tiene fondo sólido, usar `crop` para quedarse solo con el símbolo (sin el texto del ícono, que repetiría el título) y `remove_bg` con el color de ese fondo. Mirar el resultado en `work/<locale>/logo.png`.
- **Funciones:** elegir las 3 que más venden, la **novedad o diferencial** primero (`hero_chip`). 1 a 3 palabras cada una.

### 2. Elegir las capturas

Pedir al usuario la carpeta de capturas (o tomarlas con `adb exec-out screencap -p`). Mirar cada una con Read antes de elegir.

- **Centro:** la pantalla más rica y reconocible (inicio o panel con varias funciones a la vista).
- **Laterales:** dos pantallas con mucho contraste visual distinto: una con contenido (lectura, detalle) y otra con imágenes o color.
- Mismo tema (oscuro o claro) en las tres, mismo idioma que el texto de la imagen y datos realistas (contadores con números, no vacíos).
- Revisar que no haya defectos visibles: etiquetas sin procesar (`itwas/it`), textos en otro idioma, fechas mal localizadas, notificaciones, batería baja. Si hay, avisar al usuario y proponer corregirlos o tomar otra captura.
- Todas las capturas del mismo dispositivo. `screen_crop` quita la barra de estado (`top`) y la de navegación (`bottom`) en píxeles del original; para 1080x2340 suelen ser 104 y 140. Medirlo en la captura si es otro tamaño.

### 3. Escribir el config

Guardarlo junto a la salida (por ejemplo `<carpeta de imágenes>/feature-graphic/feature-graphic.json`). Las rutas relativas son relativas al config.

```json
{
  "app_name": "Mi App",
  "output_dir": ".",
  "logo": { "path": "app/src/main/ic_launcher-playstore.png", "crop": [95, 40, 420, 330], "remove_bg": "#12181A", "tolerance": 12 },
  "palette": { "bg": "#12181A", "accent": "#49CC87", "accent_soft": "#82BFAB", "deep": "#1E6B57",
               "text": "#EEF3F1", "muted": "#9AA8A4", "on_accent": "#0D1F17" },
  "fonts": { "title": "Cormorant Garamond", "title_weight": 600, "body": "Inter" },
  "screen_crop": { "top": 104, "bottom": 140 },
  "browser": "opcional: ruta a msedge.exe o chrome",
  "locales": {
    "es-419": {
      "title_lines": ["Mi", "App"],
      "title_size": 64,
      "tagline_html": "Frase corta con una <b>palabra</b> clave<br>en dos líneas.",
      "chips": ["Función estrella", "Función 2", "Función 3"],
      "hero_chip": 0,
      "screens": { "center": "capturas/es/inicio.jpg", "left": "capturas/es/a.jpg", "right": "capturas/es/b.jpg" }
    },
    "en-US": { "...": "mismo esquema, capturas en inglés" }
  }
}
```

- **Idiomas:** una entrada por código de Play (`es-419`, `es-ES`, `en-US`, `pt-BR`...). Cada idioma lleva sus propias capturas, porque una captura en inglés con texto en español se nota.
- **Nombre:** la marca no se traduce (Bible Versions sigue igual en español), salvo que la app tenga otro nombre en ese idioma.
- **Lema:** 6 a 9 palabras, natural en cada idioma (no traducción literal), cortado a mano con `<br>` en 2 líneas equilibradas, una palabra clave en `<b>`.
- **Etiquetas:** máximo 3, sin emojis (se ven baratos aquí). Si un idioma es más largo y no caben en una fila, acortarlas antes que dejar que pasen a dos filas.
- **Tipografía:** serif elegante para el título (`Cormorant Garamond`, `Playfair Display`, `Fraunces`) y sans limpia para el resto (`Inter`). Apps juveniles o técnicas: título sans geométrica (`Poppins`, `Manrope`, 700). Se cargan de Google Fonts, así que se necesita internet. Títulos largos: bajar `title_size` (56 o 48) o ponerlos en una sola línea.

### 4. Generar

```bash
python -I ~/.claude/skills/play-feature-graphic/scripts/build_feature_graphic.py <config.json>
python -I ~/.claude/skills/play-feature-graphic/scripts/build_feature_graphic.py <config.json> --locale es-419
```

Salida: `<output_dir>/feature-graphic-<locale>.png` y `work/<locale>/` (capturas recortadas, logo y el `feature.html` renderizado, útil para ajustes finos).

Requisitos: Python 3 con Pillow, Edge o Chrome. En Windows, Edge ya viene instalado.

### 5. Revisar (siempre, con Read sobre el PNG)

- [ ] 1024x500 (el script falla si no).
- [ ] Nada se corta en los bordes; el teléfono derecho se ve entero.
- [ ] El texto no toca los teléfonos; el lema no deja una palabra sola en una línea; las etiquetas en una fila.
- [ ] Tildes y caracteres especiales bien (si salen cuadros, la fuente no los tiene: cambiarla).
- [ ] El logo se ve limpio, sin halo del fondo (si lo hay, subir `tolerance`).
- [ ] Las capturas no muestran defectos (paso 2).
- [ ] Legible al reducirla a ~360 px de ancho.

Si algo falla, ajustar el config (o, para cambios de composición, `templates/feature.html`: posiciones `.p-center`, `.p-left`, `.p-right`, ancho de `.copy`) y regenerar. Mostrar el resultado al usuario y dejar la ruta completa del PNG.

## Archivos

- `scripts/build_feature_graphic.py`: el generador.
- `templates/feature.html`: la composición (placeholders `$nombre` de `string.Template`; no usar `$` literal en el CSS).
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
