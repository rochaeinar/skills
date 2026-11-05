# Idiomas: traducciones al final

**Fuente de los idiomas**: los del diseño. Por defecto son los 30 del skill `app-screen-design` (`~/.claude/skills/app-screen-design/references/idiomas.md`, que se arma desde `D:\Documents\BibleVersions\Modules\idiomas-tracker.md` quitando los que no tienen ficha en Play). Si `design/strings/` o `design/decisiones.md` dicen otra lista, manda el diseño. La tabla de abajo es una copia para trabajar sin depender del otro skill; si difieren, gana la del diseño.

**Cuándo**: durante la implementación solo existe el inglés (`values/strings.xml`). Las traducciones se hacen **recién al final**, con todas las pantallas terminadas y los textos congelados, porque cada cambio de un texto obliga a retraducirlo en todos los idiomas.

| # | Idioma | Play Console | Android | Escritura | Qué probar |
|---|---|---|---|---|---|
| 1 | Inglés (base) | en-US | `values` | Latina | Base |
| 2 | Español | es-419 (y es-ES) | `values-es` | Latina | +20-30 % |
| 3 | Portugués (Brasil) | pt-BR | `values-pt-rBR` | Latina | +20-30 % |
| 4 | Francés | fr-FR | `values-fr` | Latina | Espacio antes de `: ? !` |
| 5 | Indonesio | id | `values-in` (código antiguo) | Latina | Palabras largas |
| 6 | Filipino | fil | `values-fil` (o `values-tl`, lo que use el proyecto) | Latina | +30 % |
| 7 | Swahili | sw | `values-sw` | Latina | Revisión nativa |
| 8 | Hindi | hi-IN | `values-hi` | Devanagari | Línea alta |
| 9 | Coreano | ko-KR | `values-ko` | Hangul | Corte por palabra |
| 10 | Ruso | ru-RU | `values-ru` | Cirílica | Plurales `one/few/many/other` |
| 11 | Alemán | de-DE | `values-de` | Latina | **Texto largo** |
| 12 | Italiano | it-IT | `values-it` | Latina | |
| 13 | Amárico | am | `values-am` | Ge'ez | Fuente Noto Sans Ethiopic; revisión nativa |
| 14 | Tamil | ta-IN | `values-ta` | Tamil | Muy largo |
| 15 | Telugu | te-IN | `values-te` | Telugu | Línea alta |
| 16 | Malayalam | ml-IN | `values-ml` | Malayalam | Muy largo |
| 17 | Chino simplificado | zh-CN | `values-zh-rCN` | Han | Interlineado |
| 18 | Chino tradicional | zh-TW | `values-zh-rTW` | Han | Interlineado |
| 19 | Ucraniano | uk | `values-uk` | Cirílica | Plurales |
| 20 | Rumano | ro | `values-ro` | Latina | ș, ț |
| 21 | Polaco | pl-PL | `values-pl` | Latina | Plurales |
| 22 | Vietnamita | vi | `values-vi` | Latina | Diacríticos apilados |
| 23 | Afrikáans | af | `values-af` | Latina | Revisión nativa |
| 24 | Zulú | zu | `values-zu` | Latina | Palabras muy largas; revisión nativa |
| 25 | Birmano | my-MM | `values-my` | Birmana | **Escritura compleja**; Unicode; revisión nativa |
| 26 | Árabe | ar | `values-ar` | Árabe | **RTL** |
| 27 | Persa | fa | `values-fa` | Árabe | **RTL**; dígitos persas |
| 28 | Nepalí | ne-NP | `values-ne` | Devanagari | Revisión nativa |
| 29 | Canarés | kn-IN | `values-kn` | Kannada | Largo; revisión nativa |
| 30 | Japonés | ja-JP | `values-ja` | Kanji/Kana | Corte por carácter |

## Pasos (fase 6, antes del QA)
1. Congelar el inglés: `values/strings.xml` con todas las claves del diseño y las que agregó la implementación.
2. Para cada idioma: si existe `design/strings/<idioma>.json`, usarlo; traducir solo lo que falta o cambió respecto de `design/strings/en.json`. Traducción natural, con el tono del diseño, sin traducir nombres de la marca ni marcadores (`%1$s`, `%d`).
3. Generar `values-<código>/strings.xml`: escapar `'` y `"`, `<plurals>` con las categorías de cada idioma (ruso, polaco y ucraniano `one/few/many/other`; árabe `zero/one/two/few/many/other`; japonés, chino, coreano, vietnamita e indonesio solo `other`).
4. `res/xml/locales_config.xml` con los 30 y `android:localeConfig` en el manifiesto (idioma por app en Android 13+); `resourceConfigurations`/`localeFilters` en Gradle con la misma lista.
5. Fuentes de respaldo para las escrituras no latinas si la tipografía de marca es solo latina (familia Noto, como en el diseño).
6. `python scripts/validar_strings.py app/src/main/res`: cero errores.
7. Los idiomas de menos recursos (marcados "revisión nativa") se anotan en `impl/qa-informe.md` §Pendiente del usuario.
8. QA de idiomas: Maestro `adaptive/` en alemán, árabe (RTL espejado), hindi o birmano y japonés; capturas de las pantallas con más texto; ningún texto cortado, superpuesto ni en inglés.
