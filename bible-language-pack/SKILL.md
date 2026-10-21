---
name: bible-language-pack
description: Agrega un idioma nuevo a Bible Versions, un idioma a la vez - elige las Biblias descargadas (BibleVersionsSelected, bibles-manifest.json), las limpia y convierte a la numeración de la app (versificación KJV, con las tablas de SIL), las valida como un ingeniero de calidad (estructura, versículos faltantes o de más, numeración corrida, codificación, marcas, escritura, palabras pegadas, comparación entre copias, licencia, salud doctrinal del healthReport) con un reporte y una hoja de revisión, luego un paso de criterio pastoral evangélico (corrige solo erratas de digitalización con la misma versión en línea como prueba, compara con la RV1960 y la KJV, juzga los versículos doctrinales y deja una bitácora de cada decisión; nunca cambia ni inventa texto bíblico), y genera el paquete .obb que la app descarga de Cloudflare (la Biblia en el idioma; quiz, reflexión, referencias, comentario y planes en inglés por ahora), lo sube a R2 y lo agrega a manifest.json. Úsalo cuando pidan "agregar el idioma X", "validar la Biblia en X", "generar el módulo/paquete de X", "subir el idioma X a Cloudflare" o "siguiente idioma del tracker".
---

# Paquetes de idioma de Bible Versions

Todo pasa por `scripts/pack.py` (con `python`). Rutas en `scripts/config.json` (por PC; `SETUP.md`). Datos de entrada:

- **Biblias**: `D:\Documents\BibleVersions\BibleVersionsSelected\<XX-Idioma>\bibles\` y su catálogo `bibles-manifest.json` (las descarga `download_bibles.py` de esa carpeta).
- **Tracker**: `D:\Documents\BibleVersions\idiomas-tracker.md` (código, escritura, si permite anuncios; el skill actualiza la columna **Texto** y la bitácora).
- **Salud doctrinal**: `D:\Documents\BibleVersions\healthReport.md`. Las Biblias de "Biblias eliminadas" **no se pueden importar**; las marcadas ⚠️ salen como advertencia.
- **App**: `D:\Projects\Android\bible-versions` (`cdn/bible/manifest.json`, `cdn/bible/module-ids.json`).

Trabajo de cada idioma: `D:\Documents\BibleVersions\packs\<código>\` (`pack.json`, `work.db`, `report.md`, `review.html`, `build/`, `<idioma>-vN.obb`, `app-integration.md`).

## Cómo es un paquete (lo que la app espera)

- Un **zip plano** con extensión `.obb`. `LanguageDownloader` lo baja de `https://cdn.timelesslabs.app/bible/<url del manifest>`, comprueba tamaño y SHA-256 y lo descomprime en la carpeta de módulos. `ModuleInitializer.saveModuleInformation` registra **cada archivo** según su extensión (`.bblx` Biblia, `.cmtx` comentario, `quiz*.db`, `coffee*.dev`, `references*.db`) leyendo la tabla `Details` (una fila: `Id`, `Language`, `Abbreviation`, `Description`).
- **`Details.Id` es global**: nunca se repite ni se reutiliza. El registro es `cdn/bible/module-ids.json` (ids 1–49 los paquetes es/esp/en; los nuevos desde 100).
- `.bblx`: tablas `Details` y `Bible(id, Book 1-66, Chapter, Verse, Scripture)`, numeración KJV (la de `R.array.chapter_count`). El texto se muestra como **RTF**: sin `{`, `}` ni `\` sueltos (el import los reemplaza).
- **Por ahora**: la Biblia en el idioma; `quiz_en.db` (44), `coffee_en.dev` (43), `references_en.db` (47), `jamieson-fausset-brown.cmtx` (37) y los 3 planes, copiados del paquete inglés con los mismos nombres e ids.

## Flujo, un idioma a la vez

1. **`pack.py status`**: idiomas del tracker y en qué paso está cada uno. Elegir el siguiente con el usuario (los ✅ "¿Con anuncios?" primero).
2. **`pack.py init <código>`** (p. ej. `fr`, `pt-BR`, `zh-Hans`): crea `pack.json` con todas las Biblias de ese idioma del manifiesto, marca las rechazadas y las no comerciales, y preselecciona una. **Editar `pack.json`**:
   - `include: true` en las que van (1–3; si dos fuentes tienen el mismo texto, incluir las dos al principio sirve para compararlas y luego dejar la mejor).
   - `abbreviation` (la sigla habitual en ese idioma: `LSG`, `ARC`, `СП`) y `description` (nombre en el idioma).
   - `attribution`: el texto de créditos que exige la licencia (va en `Details.Comments`); revisarlo con la página de licencia del manifiesto.
   - `default_bible`: el id de la principal (completa, de equivalencia formal si se puede, apta para anuncios si el tracker lo pide).
   - `module_language`: el código que usa la app (`pt`, `fil`, `zh-hans`…); viene propuesto.
3. **`pack.py import <código>`**: lee cada Biblia (VPL de eBible o SQLite de Bible SuperSearch), descarta los libros fuera de los 66, **detecta la numeración capítulo por capítulo** (eng, org hebrea, rso sinodal, lxx, vul, rsc: tablas `.vrs` de SIL en `assets/vrs/`) y la convierte a la de la app. Los títulos de los Salmos (versículo 0) se unen al versículo 1, como en el módulo KJV. Limpia y anota: NFC, marcas de numeración original (`[3:19]`, `(22:1)`), USFM, HTML, `¶`, espacios.
4. **`pack.py validate <código>`** → `report.md` (errores, advertencias, notas), `issues.json` (lo mismo, para el paso de criterio) y `review.html` (hoja de revisión: versículos clave junto a la RV1960 y la KJV, 30 al azar y la bitácora de criterio). Sale con código 1 si hay errores. Si una Biblia tiene muchos errores de estructura, probar antes otra fuente u opciones de `pack.json` (tabla de abajo).
5. **Paso de criterio (lo hago yo, como pastor evangélico)**: ver la sección siguiente. Termina con todos los problemas y versículos clave decididos y anotados.
6. **`pack.py approve <código> --by "Claude (criterio pastoral)" [--notes ...]`**: exige 0 errores, cada error y advertencia de la última validación decidido en `criteria.json`, cada versículo clave con veredicto y ninguno en `problema`. Guarda la huella de `work.db` (si algo cambia después, hay que validar y aprobar de nuevo). Tracker: Texto 🟦. Mostrarle al usuario el resumen de la bitácora (cuántas correcciones, de qué tipo, los matices doctrinales) antes de seguir.
7. **`pack.py build <código>`**: escribe los `.bblx` (ids nuevos en `module-ids.json`), copia los módulos ingleses, arma `<idioma>-vN.obb` (N = siguiente versión si ya hay una en el manifiesto) y **lo verifica como lo lee la app** (zip plano, una fila en `Details`, ids únicos y no usados por otro idioma, `Language` correcto, ≥7.000 versículos, sin caracteres RTF). Escribe `app-integration.md`. Tracker: Texto ✅.
8. **`pack.py publish <código>`** muestra el plan; **con permiso explícito del usuario**: `--yes` sube el `.obb` a R2 (`timelesslabs-cdn/bible/modules/`), comprueba que el CDN lo sirve con ese tamaño y agrega `languages.<código>` a `cdn/bible/manifest.json` (local). El manifiesto se publica después con `.\scripts\publish-manifest.ps1 -DryRun` y luego sin `-DryRun` (desde la raíz de la app), también con permiso.
9. **La app**: seguir `app-integration.md` (`LanguageConfig`, nombre del idioma, idioma del teléfono, TTS) y probar en el teléfono con la build debug antes de un release (`android-release`). Sin eso, el manifiesto con el idioma nuevo no le hace nada a la app actual.

## Paso de criterio (pastoral)

El usuario no conoce los idiomas: **el criterio lo pongo yo**, como un pastor evangélico de sana doctrina, con la **Reina-Valera 1960** (local: `ES-Spanish\reina-valera-1960.bblx`) y la **KJV** (local) como vara de medir. La regla de oro: **no se cambia la Biblia**. Solo se corrigen errores de digitalización (palabras pegadas, letras o palabras perdidas al copiar), y siempre con la **misma versión** como prueba. **Nunca se inventa ni se reescribe texto bíblico**, ni para "mejorarlo" doctrinalmente.

1. **`pack.py criteria <código> [--fetch 150]`** crea o actualiza `criteria.json`:
   - un registro por cada error y advertencia de la última validación (los que ya no aparecen pasan a `resolved`, con su historia);
   - un registro por cada versículo clave (`assets/review-verses.json`) y Biblia, con el texto, la RV1960 y la KJV;
   - **evidencia**: el mismo versículo en la otra copia descargada de la misma versión (si hay, primero y sin internet) y en la misma versión en línea (`assets/verify-sources.json`: getBible, Bolls y Bible.com, ya investigados para todas las Biblias del tracker; `without_online_copy` lista las que no tienen copia en línea). Busca por número y, si el sitio numera distinto, por el texto más parecido del capítulo;
   - una **propuesta** automática por problema (nunca una decisión).

   Internet con cuidado: cada capítulo se pide **una sola vez** (caché en `packs\_cache\`), con pausas por sitio (1,5–4 s), un máximo de pedidos por corrida (`--fetch`) y, si un sitio responde 403/429, no se le vuelve a pedir en esa corrida. Bible.com es el último recurso: es el endpoint de su propia web, no una API pública.
2. **`pack.py verify <código> "<LIB C:V>" [--bible id]`**: un versículo concreto en nuestras copias, en la misma versión en las tres webs, en la RV1960 y en la KJV. Para las dudas puntuales.
3. **Decido cada registro** en `criteria.json` (`decision`: `action` + `note` obligatoria, que es la bitácora):

   | Acción | Cuándo | Qué permite el script |
   |---|---|---|
   | `split_words` (`word`, `into`) | Palabras pegadas («тыблагословил») | Solo agregar un espacio: si cambia cualquier letra, se rechaza |
   | `use_source` (`source`) | Dos copias de la misma versión difieren y una tiene la errata | Copiar el versículo de la otra copia descargada |
   | `override` (`evidence`: índice) | Falta texto o hay erratas y la misma versión en línea lo tiene bien | Copiar el texto exacto de esa evidencia. Si es `probable`, otra fuente o la otra copia tiene que decir lo mismo. Si el sitio lo numera distinto: `renumbered_ok: true` después de comprobar que es el mismo versículo |
   | `drop_extra` / `append_extra` | Versículo de más que no está en la RV1960 ni en la KJV (adiciones de la Septuaginta) | Descartarlo o unirlo al último versículo del capítulo |
   | `accept` | Advertencia que está bien (una palabra real, un largo normal en esa traducción, un versículo que esa versión no tiene) | Nada cambia; queda anotado |
   | `reject_bible` | La Biblia no sirve (calidad o doctrina) | La quita del paquete |

   Para muchas advertencias del mismo tipo que ya revisé (p. ej. 40 "longitud" de una paráfrasis), `bulk: [{"check": "longitud", "bible": "*", "action": "accept", "note": "..."}]` decide las que siguen sin decisión, con esa nota.
4. **Versículos clave**: `verdict` = `ok` (dice lo mismo que el original), `matiz` (fiel en lo esencial, con un matiz que hay que conocer: se anota y, si es nuevo, se agrega al healthReport) o `problema` (contradice la doctrina: no se corrige el texto; se rechaza esa Biblia o se consulta al usuario). En `note`, en español, qué dice el versículo y por qué está bien o no. Criterio doctrinal: la Trinidad y la divinidad de Cristo, salvación por gracia mediante la fe sin obras, un solo mediador, sin imágenes, sin purgatorio, la Escritura sola, el canon de 66 libros, la virginidad de María en el nacimiento de Jesús ("hasta que", "primogénito").
5. **`pack.py apply <código>`**: aplica las decisiones a `pack.json` (`criteria_overrides`, `extra_verses_refs`, `include`), se niega entera si alguna rompe las reglas de la tabla, y vuelve a importar, validar y actualizar `criteria.json`. Repetir 3–5 hasta que no queden problemas sin decidir ni errores.

La bitácora queda en `criteria.json` y en `review.html`, en la columna **Bitácora de criterio** y en la tabla **Problemas del reporte y cómo se resolvieron**, con enlaces a la evidencia.

## Controles de la validación y cómo resolverlos

| Control | Nivel | Qué significa | Qué hacer |
|---|---|---|---|
| salud | E/W | Rechazada en healthReport / tiene una observación ⚠️ | E: quitarla. W: citar la observación al usuario |
| licencia | E/W | Sin licencia o atribución, o no comercial en un idioma con anuncios | Completar `attribution`; NC: solo si la app sigue sin anuncios (decisión del usuario) |
| módulo | E | Falta `abbreviation` o `default_bible` | Completar `pack.json` |
| estructura | E/W | Libro, capítulo o versículo vacío o faltante | E: buscar la causa (numeración, fuente incompleta). W si es un versículo que el texto crítico omite (Mt 17:21…) o un versículo combinado con el anterior |
| versificación | E | Versículo de más, que la app no mostraría | Si es una adición de la Septuaginta (Jos 24:34-36, Pr 4:28-29 en la Sinodal): `"extra_verses": "drop"` en esa Biblia. Si es numeración corrida: `"versification": {"JOB 39": "org"}` o usar otra fuente |
| alineación | W | Los largos de los versículos de un capítulo no siguen a la KJV: posible numeración corrida | Comparar ese capítulo en `work.db` con la KJV |
| codificación | E | Mojibake (`Ã©`, `â€`, `�`) | Otra fuente o volver a descargar |
| marcas | E | Quedan `\w`, `<...>`, llaves | Agregar la regla en `CLEAN_RULES` y reimportar |
| escritura | E/W | Letras fuera de la escritura del tracker (p. ej. la Cornilescu de eBible está en cirílico) | Otra fuente, o corregir la escritura en el tracker si estaba mal |
| errata | W | Palabra rara que son dos frecuentes pegadas («тыблагословил») | Si hay otra copia del mismo texto, usar la que no la tiene; si no, `overrides` |
| comparación | W | Dos copias del mismo texto difieren un poco en un versículo | Casi siempre una de las dos tiene la errata: elegir la buena |
| repetición, puntuación, longitud | W | Palabra larga repetida, paréntesis sin cerrar en el capítulo, largo anormal | Mirar el versículo; casi siempre es correcto |
| corrección manual | W | Un `overrides` aplicado | Que el usuario lo vea |

**Correcciones a mano** (`"overrides"` en `pack.json`): no se usan. Toda corrección pasa por el paso de criterio, que exige evidencia de la misma versión y deja la bitácora; los matices doctrinales anotados en healthReport **nunca** se corrigen.

## Reglas

- Un idioma a la vez, y nada se publica sin **0 errores + paso de criterio completo + `approve` + `--yes`**, después de que el usuario vio el resumen de la bitácora y el plan.
- Solo Biblias del tracker y del healthReport (evangélicas, respaldadas por una organización confiable; memoria `biblias-evangelicas`). Si aparece una nueva, primero va al healthReport.
- Claves: la de Cloudflare está en el Administrador de credenciales (`BibleVersions-Cloudflare`); `publish` la lee sin mostrarla. Nunca en el chat ni en archivos.
- `work.db`, los reportes y los `.obb` quedan en `packs\<código>\` (fuera de los repos). `module-ids.json` sí va en el repo de la app: hacer commit cuando el usuario lo pida.
- Pruebas sin tocar el tracker real: `BIBLE_PACK_CONFIG=<otro config.json>` con rutas a copias.

## Archivos

- `scripts/pack.py`: todo el flujo. `scripts/config.json`: rutas de esta PC (no va al respaldo).
- `assets/vrs/*.vrs`: versificaciones de Paratext (de `sil-machine`, licencia MIT de SIL Global, `assets/vrs/LICENSE`).
- `assets/review-verses.json`: los versículos de la revisión humana.
- Respaldo: `D:\Projects\skills\bible-language-pack` (copiar después de cada cambio).
