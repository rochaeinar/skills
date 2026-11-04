# Idiomas del diseño (30)

Salen de `D:\Documents\BibleVersions\Modules\idiomas-tracker.md` (50 idiomas), **quitando los que no tienen ficha propia en Google Play** (yoruba, igbo, hausa, cebuano, criollo haitiano, twi, shona, kinyarwanda, luganda, lingala, malgache, oromo, tigriña, xhosa, ilocano, hiligaynon, tok pisin, quechua, aimara, guaraní). **Inglés por defecto.** Si el tracker cambia, volver a filtrarlo con la lista de idiomas de la ficha de Play Console.

| # | Idioma | Play Console | Android `values-` | Escritura | Notas para el diseño |
|---|---|---|---|---|---|
| 1 | Inglés (por defecto) | en-US | `values` | Latina | Idioma base de todos los cuadros |
| 2 | Español | es-419 (y es-ES) | `values-es` | Latina | +20-30 % de largo |
| 3 | Portugués (Brasil) | pt-BR | `values-pt-rBR` | Latina | +20-30 % |
| 4 | Francés | fr-FR | `values-fr` | Latina | +20-30 %; espacio antes de `: ? !` |
| 5 | Indonesio | id | `values-in` (Android usa el código antiguo `in`) | Latina | Palabras largas |
| 6 | Filipino / tagalo | fil | `values-fil` (o `values-tl`, ver lo que usa el proyecto) | Latina | +30 % |
| 7 | Swahili | sw | `values-sw` | Latina | |
| 8 | Hindi | hi-IN | `values-hi` | Devanagari | Línea más alta (matras); probar escritura compleja |
| 9 | Coreano | ko-KR | `values-ko` | Hangul | Corte de línea por palabra |
| 10 | Ruso | ru-RU | `values-ru` | Cirílica | +30 %, palabras largas; plurales complejos |
| 11 | Alemán | de-DE | `values-de` | Latina | **Prueba de texto largo** (+35 %, compuestos sin guiones) |
| 12 | Italiano | it-IT | `values-it` | Latina | +20 % |
| 13 | Amárico | am | `values-am` | Ge'ez | Fuente especial (Noto Sans Ethiopic) |
| 14 | Tamil | ta-IN | `values-ta` | Tamil | Uno de los más largos (+40-60 %) |
| 15 | Telugu | te-IN | `values-te` | Telugu | Línea alta |
| 16 | Malayalam | ml-IN | `values-ml` | Malayalam | Muy largo (+50 %) |
| 17 | Chino simplificado | zh-CN | `values-zh-rCN` | Han | Más corto; necesita interlineado mayor |
| 18 | Chino tradicional | zh-TW | `values-zh-rTW` | Han | Ídem |
| 19 | Ucraniano | uk | `values-uk` | Cirílica | +30 % |
| 20 | Rumano | ro | `values-ro` | Latina | Diacríticos (ș, ț) |
| 21 | Polaco | pl-PL | `values-pl` | Latina | +30 %, plurales complejos |
| 22 | Vietnamita | vi | `values-vi` | Latina | Diacríticos apilados: interlineado ≥ 1.4 |
| 23 | Afrikáans | af | `values-af` | Latina | |
| 24 | Zulú | zu | `values-zu` | Latina | Palabras muy largas |
| 25 | Birmano | my-MM | `values-my` | Birmana | **Escritura compleja**, línea muy alta; Unicode (no Zawgyi) |
| 26 | Árabe | ar | `values-ar` | Árabe | **RTL** |
| 27 | Persa | fa | `values-fa` | Árabe | **RTL**; dígitos persas |
| 28 | Nepalí | ne-NP | `values-ne` | Devanagari | Como hindi |
| 29 | Canarés | kn-IN | `values-kn` | Kannada | Largo, línea alta |
| 30 | Japonés | ja-JP | `values-ja` | Kanji/Kana | Sin espacios entre palabras: corte por carácter |

## Reglas para que el diseño aguante los 30
- **Nada de texto en imágenes.** Todos los textos son strings con clave.
- **Espacio para crecer:** etiquetas cortas +100 %, frases +40 %; botones y chips crecen o pasan a dos líneas, nunca cortan con "…" una acción. Pestañas y barras inferiores: etiquetas de 1 palabra en inglés, y probar en alemán y tamil.
- **Altura de línea flexible:** nada de alturas fijas en contenedores de texto (devanagari, birmano, telugu y vietnamita son más altos).
- **RTL (árabe, persa):** todo espejado (navegación, flechas de "atrás", deslizables, barras de progreso, orden de íconos); no se espejan los logos, los números, los reproductores de medios ni los íconos que no tienen dirección. Usar `start/end`, nunca `left/right`.
- **Formatos:** fechas, horas, números, monedas y plurales según el idioma (`DateFormat`, `NumberFormat`, `plurals`); nunca armar frases concatenando.
- **Fuentes:** la tipografía de marca suele ser solo latina: definir la alternativa (familia Noto) para cada escritura no latina.
- **Selector de idioma** (si la app lo tiene): cada idioma escrito en su propio idioma ("Deutsch", "العربية"), con buscador si son 30.

## Qué se muestra en el diseño
- Por defecto: todos los cuadros en inglés + una prueba de estrés en **alemán**, **árabe** y **hindi o birmano** de las pantallas con más texto (y de la barra de navegación).
- Si en la fase 3 se acordó: catálogo `strings/<idioma>.json` (y `values-*/strings.xml`) en los 30 idiomas, traducciones naturales, con los de menos recursos (amárico, zulú, birmano, nepalí, canarés, swahili, afrikáans) marcados para revisión de un nativo.
