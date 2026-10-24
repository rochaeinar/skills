---
name: bible-language-pack
description: Paso 2 de 5 del flujo de idiomas de Bible Versions (Modules/README.md) - un idioma a la vez, elige las Biblias descargadas (Modules/languages/<idioma>/sources, manifest.json), las limpia y convierte a la numeración de la app (versificación KJV, con las tablas de SIL), las valida como un ingeniero de calidad (estructura, versículos faltantes o de más, numeración corrida, codificación, marcas, escritura, palabras pegadas, comparación entre copias, licencia, salud doctrinal del healthReport) con un reporte y una hoja de revisión, luego un paso de criterio pastoral evangélico (corrige solo erratas de digitalización con la misma versión en línea como prueba, compara con la RV1960 y la KJV, juzga los versículos doctrinales y deja una bitácora de cada decisión; nunca cambia ni inventa texto bíblico), y arma el paquete .obb que la app descarga de Cloudflare (la Biblia en el idioma + lo compartido de Modules/common) en Modules/cdn/bible/modules con la regla de versiones; también los paquetes base en, es y es-lite. No descarga (bible-download), no traduce la reflexión (bible-devotional-translate) ni sube a R2 (bible-language-ship). Úsalo cuando pidan "agregar el idioma X", "validar la Biblia en X", "generar el módulo/paquete de X", "rearmar el paquete inglés/español" o "siguiente idioma del tracker".
---

# Paquetes de idioma de Bible Versions

**Paso 2 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md` (estructura, todos los skills y quién escribe cada archivo). Viene después de **bible-download** (paso 1: las Biblias en `sources\`); sigue **bible-devotional-translate** (paso 3, la reflexión) o **bible-language-ship** (paso 4). Si falta algo del paso anterior, decirlo y nombrar el skill que lo produce; nunca ejecutarlo desde aquí.

Todo pasa por `scripts/pack.py` (con `python`). Config: `Modules\config.json` (`SETUP.md`); todas las rutas salen de esa carpeta. Datos de entrada:

- **Biblias**: `Modules\languages\<código>\sources\` y su catálogo `Modules\languages\manifest.json` (las baja el skill bible-download).
- **Tracker**: `Modules\idiomas-tracker.md` (código, escritura, si permite anuncios; el skill actualiza la columna **Texto** y la bitácora).
- **Salud doctrinal**: `Modules\healthReport.md`. Las Biblias de "Biblias eliminadas" **no se pueden importar**; las marcadas ⚠️ salen como advertencia.
- **App**: `D:\Projects\Android\bible-versions` (`cdn/bible/manifest.json`, `cdn/bible/module-ids.json`).

Trabajo de cada idioma: `Modules\languages\<código>\` (`pack.json`, `work\work.db`, `report.md`, `review.html`, `criteria.json`, `app-integration.md`, y los `.bblx` en `modules\`). El `.obb` va a `Modules\cdn\bible\modules\<código>-vN.obb` (no hay `build\`: se arma en una carpeta temporal).

## Cómo es un paquete (lo que la app espera)

- Un **zip plano** con extensión `.obb`. `LanguageDownloader` lo baja de `https://cdn.timelesslabs.app/bible/<url del manifest>`, comprueba tamaño y SHA-256 y lo descomprime en la carpeta de módulos. `ModuleInitializer.saveModuleInformation` registra **cada archivo** según su extensión (`.bblx` Biblia, `.cmtx` comentario, `quiz*.db`, `coffee*.dev`, `references*.db`) leyendo la tabla `Details` (una fila: `Id`, `Language`, `Abbreviation`, `Description`).
- **`Details.Id` es global**: nunca se repite ni se reutiliza. El registro es `cdn/bible/module-ids.json` (ids 1–49 los paquetes es/esp/en; los nuevos desde 100).
- `.bblx`: tablas `Details` y `Bible(id, Book 1-66, Chapter, Verse, Scripture)`, numeración KJV (la de `R.array.chapter_count`). El texto se muestra como **RTF**: sin `{`, `}` ni `\` sueltos (el import los reemplaza).
- **Lo que lleva además de las Biblias**: la lista `contents` de `pack.json` (`{"from": "common/en", "file": "quiz_en.db"}`): `common/en` quiz_en (44), coffee_en (43), references_en (47), JFB (37) y `common/all` los 3 planes, una sola copia en `Modules\common\` para todos los paquetes. Lo propio del idioma va con `"from": "modules"`.
- **Reflexión traducida** (skill `bible-devotional-translate`): `languages\<código>\modules\coffee_<código>.dev` con su Id propio; ese skill cambia en `contents` la entrada `common/en coffee_en.dev` por `modules coffee_<código>.dev`.
- **Paquetes base** `en`, `es` y `es-lite` (código `esp` en la CDN): `pack.json` con `"kind": "base"`, sin Biblias importadas; `contents` lista todo (sus `.bblx` y `.cmtx` en `modules\`, lo compartido en `common\`). Se rearman con `pack.py build en | es | es-lite`.

## Flujo, un idioma a la vez

1. **`pack.py status`**: idiomas del tracker y en qué paso está cada uno. Elegir el siguiente con el usuario (los ✅ "¿Con anuncios?" primero).
2. **`pack.py init <código>`** (p. ej. `fr`, `pt-BR`, `zh-Hans`): crea `pack.json` con todas las Biblias de ese idioma del manifiesto, marca las rechazadas y las no comerciales, y preselecciona una. **Editar `pack.json`**:
   - `include: true` en las que van (1–3; si dos fuentes tienen el mismo texto, incluir las dos al principio sirve para compararlas y luego dejar la mejor).
   - `abbreviation` (la sigla habitual en ese idioma: `LSG`, `ARC`, `СП`) y `description` (nombre en el idioma).
   - `attribution`: el texto de créditos que exige la licencia (va en `Details.Comments`); revisarlo con la página de licencia del manifiesto.
   - `default_bible`: el id de la principal (completa, de equivalencia formal si se puede, apta para anuncios si el tracker lo pide).
   - `module_language`: el código que usa la app (`pt`, `fil`, `zh-hans`…); viene propuesto.
   - **Si hay una copia mejor de la misma versión en getBible** (`assets/verify-sources.json`): pedir al skill bible-download `download.py getbible <abbr> --lang <código>`: la baja **en un solo pedido** (la Biblia entera), la agrega al manifiesto y a `pack.json`. Ejemplo: la Sinodal de getBible (Sociedad Bíblica Rusa vía CrossWire) conserva los corchetes que la de eBible perdió.
   - **`"role": "reference"`** en una Biblia de `pack.json`: se importa y se compara (y sirve para `use_source`), pero no se valida ni se publica. Útil para la edición canónica de la misma traducción.
   - **Biblias con licencia (no comercial, permiso de la editorial)** — decisión del usuario (2026-10-21): se preparan igual, pero con `"licence_review": {"status": "pendiente", "countries": ["ZA", "NA"], "reason": "…"}` en `pack.json`. La validación lo anota, `build` deja el tracker en 🟨 («pendiente de revisión de licencia») y **`ship.py cdn` (bible-language-ship) se niega a subirlo** hasta que el usuario lo apruebe (`"status": "aprobada"`), y entonces solo para esos países. Con licencia **ND** (sin obras derivadas) no se corrige el texto (ni erratas ni palabras pegadas): solo numeración. Las que solo existen en Bible.com no se descargan de ahí (sus textos tienen licencia): quedan 🟨 en el tracker, para pedir permiso y texto a la Sociedad Bíblica.
   - Antes de dar un idioma por «sin Biblia libre», revisar también los catálogos de getBible (`api.getbible.net/v2/translations.json`) y Bolls: así apareció la malgache 1865 de dominio público.
3. **`pack.py import <código>`**: lee cada Biblia (VPL de eBible, **USFM de eBible** si el archivo termina en `_usfm.zip`, JSON de getBible o SQLite de Bible SuperSearch), descarta los libros fuera de los 66, **detecta la numeración capítulo por capítulo** (eng, org hebrea, rso sinodal, lxx, vul, rsc: tablas `.vrs` de SIL en `assets/vrs/`) y la convierte a la de la app. Los títulos de los Salmos (versículo 0) se unen al versículo 1, como en el módulo KJV. Los **agregados deuterocanónicos dentro de libros canónicos** que la tabla manda a otro libro (Daniel 3:24-90, Daniel 13-14, Salmo 151) se descartan y se anotan. Si dos versículos caen en el mismo número, el segundo pasa al siguiente libre. `VRS_FIXES` corrige líneas erróneas de las tablas de SIL (verificadas contra la RV1960). Limpia y anota: NFC, marcas de numeración original (`[3:19]`, `(22:1)`), USFM, HTML, `¶`, espacios, marcas de nota (`*✶✝`, Darby), `‘br…’`, y un versículo hecho solo de `- - -` (BSS: versículo combinado) queda vacío.
   - **Limpiezas por Biblia en `pack.json`** (se aplican al importar, se anotan y se niegan si cambian letras o dígitos donde no deben):
     - `"typography": [[regex, reemplazo], …]`: solo puntuación y espacios (`,,`→`„`, espacios antes de clíticos, `? ` antes de puntuación CJK). Si cambia una letra o un dígito, el import se corta.
     - `"editor_notes": [regex, …]`: quita notas del editor que ocupan un paréntesis entero («(Sau: …)», «(0365 an)»), nunca texto suelto.
     - `"encoding_fixes": [[de, a], …]`: pares literales de 1–3 caracteres al comienzo de palabra (VNI vietnamita: `K”`→…).
     - `"stray_marks": ["S"]`: quita un token suelto exacto de 1–3 caracteres (marcas de la fuente, NBG polaca; el `_` de la ULB cebuana).
     - `"repeated_verses": "empty"`: si un versículo repite exactamente el texto del anterior (la fuente copió el texto de un rango en cada número: Judson y Bungo-yaku de getBible), se deja en el primero y los demás quedan vacíos (combinados).
     - `"colophon": regex`: quita el colofón del impresor pegado al último versículo de cada libro («… ကျမ်းပြီး၏», «fin del libro de…»; Judson). Solo en el último versículo con texto de cada libro.
     - Ya en `CLEAN_RULES`: `cjk_space` (espacios ASCII entre caracteres chinos); quedan vacíos el placeholder `a` de CrossWire (versículo unido) y el «POSSIBLE ERROR IN BIBLE, TEXT MISSING HERE» de BSS (versículo perdido: tomarlo de otra copia).
   - **Marcas de versículos combinados en las ULB** (Door43): `-` o `_` en lugar del texto = el contenido está en el versículo vecino (1 Cr 8:18 trae la lista de 8:17-18), **no** versículos sin traducir. Revisar también los versículos que el texto crítico omite: a veces la ULB corre el número (Mt 18:10 en el 11, Ro 16:23 en el 24, el final de Jn 5:3 como 5:4) y se corrige con `move`/`join`.
   - **getBible frente a BSS**: getBible suele traer los títulos de los Salmos y versículos que BSS perdió, pero rellena los rangos repitiendo el texto; BSS deja los combinados vacíos. Comparar las dos antes de elegir la principal.
   - La escritura del tracker puede llevar una nota entre paréntesis («Árabe (RTL)»): el control de escritura la ignora.
   - `VRS_EXTRA` agrega líneas a las tablas de SIL (p. ej. `NUM 25:19 = NUM 26:1` en `org`, que la tabla no trae).
   - **El VPL de eBible de los textos de Biblica (NVI, HCV, Neno…) pierde las líneas de poesía dentro de un versículo** (todo lo que sigue a la primera línea). Para esas Biblias, bajar el USFM (`<id>_usfm.zip` en `usfm/` del idioma) y apuntar `pack.json` a él. Al leer el USFM se quitan notas, referencias cruzadas (`\x`, `\bdit (Mat 1:2)\bdit*` y las referencias sueltas entre paréntesis al final del versículo, como en la IRV) y los rótulos de quién habla (`\k वधू\k*` en Cantares); los títulos de los Salmos (`\d`) van al versículo 1.
4. **`pack.py validate <código>`** → `report.md` (errores, advertencias, notas), `issues.json` (lo mismo, para el paso de criterio) y `review.html` (hoja de revisión: versículos clave junto a la RV1960 y la KJV, 30 al azar y la bitácora de criterio). Sale con código 1 si hay errores. Si una Biblia tiene muchos errores de estructura, probar antes otra fuente u opciones de `pack.json` (tabla de abajo).
5. **Paso de criterio (lo hago yo, como pastor evangélico)**: ver la sección siguiente. Termina con todos los problemas y versículos clave decididos y anotados.
6. **`pack.py approve <código> --by "Claude (criterio pastoral)" [--notes ...]`**: exige 0 errores, cada error y advertencia de la última validación decidido en `criteria.json`, cada versículo clave con veredicto y ninguno en `problema`. Guarda la huella de `work.db` (si algo cambia después, hay que validar y aprobar de nuevo). Tracker: Texto 🟦. Mostrarle al usuario el resumen de la bitácora (cuántas correcciones, de qué tipo, los matices doctrinales) antes de seguir.
7. **`pack.py build <código>`**: escribe los `.bblx` en `modules\` (ids nuevos en `module-ids.json`), junta lo de `contents`, arma un zip **reproducible** (mismos archivos = mismo sha256; deflate de 7-Zip si está instalado) y **lo verifica como lo lee la app** (zip plano, una fila en `Details`, ids únicos y no usados por otro idioma, `Language` correcto, ≥7.000 versículos, sin caracteres RTF). Lo deja en `Modules\cdn\bible\modules\` con la **regla de versiones** y lo anota en `cdn\bible\versions.json`:
   - sin versión anterior → `v1`;
   - la última versión **todavía no salió en un release de la app** (armada después de la fecha del `versionName` de `app/build.gradle`, `26.10.19` = 2026-10-19) → se reemplaza con el **mismo número**;
   - ya salió: mismo sha256 → se queda (`unchanged`); otro sha256 → `v(N+1)`.

   Escribe `app-integration.md`. Tracker: Texto ✅.
8. **Subir a R2 y el manifiesto ya no es de este skill**: paso 4, `ship.py cdn <código>` (bible-language-ship), con permiso explícito del usuario.
9. **La app**: seguir `app-integration.md` (`LanguageConfig`, nombre del idioma, idioma del teléfono, TTS) y probar en el teléfono con la build debug antes de un release (`android-release`). Sin eso, el manifiesto con el idioma nuevo no le hace nada a la app actual.

## Paso de criterio (pastoral)

El usuario no conoce los idiomas: **el criterio lo pongo yo**, como un pastor evangélico de sana doctrina, con la **Reina-Valera 1960** (local: `languages\es\modules\reina-valera-1960.bblx`) y la **KJV** (local) como vara de medir. La regla de oro: **no se cambia la Biblia**. Solo se corrigen errores de digitalización (palabras pegadas, letras o palabras perdidas al copiar), y siempre con la **misma versión** como prueba. **Nunca se inventa ni se reescribe texto bíblico**, ni para "mejorarlo" doctrinalmente.

1. **`pack.py criteria <código> [--fetch 150]`** crea o actualiza `criteria.json`:
   - un registro por cada error y advertencia de la última validación (los que ya no aparecen pasan a `resolved`, con su historia);
   - un registro por cada pasaje clave (`assets/review-verses.json`: **161 pasajes, 273 versículos, en 24 temas doctrinales**: Escritura, Trinidad, divinidad de Cristo, nacimiento virginal, María, expiación, resurrección, salvación por gracia, seguridad, arrepentimiento, un solo mediador, sacerdocio de los creyentes, imágenes y culto, el más allá, la Iglesia, Cena y bautismo, ministerio, tradición, Espíritu Santo, pecado, segunda venida, canon y numeración) y Biblia, con el texto, la RV1960 y la KJV;
   - un registro por cada versículo de la **muestra al azar** (80 por Biblia, siempre los mismos para esa Biblia; `review_sample` en `pack.json` lo cambia), que también necesita veredicto;
   - **evidencia**: el mismo versículo en la otra copia descargada de la misma versión (si hay, primero y sin internet) y en la misma versión en línea (`assets/verify-sources.json`: getBible, Bolls y Bible.com, ya investigados para todas las Biblias del tracker; `without_online_copy` lista las que no tienen copia en línea). Busca por número y, si el sitio numera distinto, por el texto más parecido del capítulo;
   - una **propuesta** automática por problema (nunca una decisión).

   Internet con cuidado: cada capítulo se pide **una sola vez** (caché en `Modules\_cache\`), con pausas por sitio (1,5–4 s), un máximo de pedidos por corrida (`--fetch`) y, si un sitio responde 403/429, no se le vuelve a pedir en esa corrida. Bible.com es el último recurso: es el endpoint de su propia web, no una API pública.
2. **`pack.py verify <código> "<LIB C:V>" [--bible id]`**: un versículo concreto en nuestras copias, en la misma versión en las tres webs, en la RV1960 y en la KJV. Para las dudas puntuales.
3. **Decido cada registro** en `criteria.json` (`decision`: `action` + `note` obligatoria, que es la bitácora):

   | Acción | Cuándo | Qué permite el script |
   |---|---|---|
   | `split_words` (`word`, `into`: [a, b]) | Palabras pegadas («тыблагословил», «لَابِٱلْإِيمَانِ») | Solo agregar un espacio: si cambia cualquier letra, se rechaza. `word` sin la puntuación de alrededor; los diacríticos árabes cuentan como parte de la palabra. Muchas a la vez: confirmarlas con la otra copia de la misma versión (que las escriba separadas) |
   | `use_source` (`source`) | Dos copias de la misma versión difieren y una tiene la errata | Copiar el versículo de la otra copia descargada |
   | `override` (`evidence`: índice) | Falta texto o hay erratas y la misma versión en línea lo tiene bien | Copiar el texto exacto de esa evidencia. Si es `probable`, otra fuente o la otra copia tiene que decir lo mismo. Si el sitio lo numera distinto: `renumbered_ok: true` después de comprobar que es el mismo versículo |
   | `move` (`from`, o `moves: {destino: origen}`) | La numeración quedó corrida (Salmo 116, Daniel 6 en la Sinodal) | Solo cambia el número de versículos del mismo libro (mismo capítulo o el siguiente); el texto no se toca |
   | `drop_extra` / `append_extra` | Versículo de más que no está en la RV1960 ni en la KJV (adiciones de la Septuaginta) | Descartarlo o unirlo al último versículo del capítulo |
   | `accept` | Error o advertencia que está bien (versículo combinado: el texto completo está en el anterior; título de libro impreso como encabezado). Un error aceptado figura como "ACEPTADO POR CRITERIO" y no bloquea | Nada cambia; queda anotado |
   | `accept` (advertencias) | Advertencia que está bien (una palabra real, un largo normal en esa traducción, un versículo que esa versión no tiene) | Nada cambia; queda anotado |
   | `reject_bible` | La Biblia no sirve (calidad o doctrina) | La quita del paquete |
   | `join` (`joins: ["ACT 24:19"]`) | La fuente partió en dos un versículo de la KJV (se aplica antes de los `move`, que usan la numeración ya unida) | Une cada versículo, en orden, al anterior que todavía tiene texto (dos versículos de título de un Salmo terminan enteros en el 1); el versículo 1 se une al último del capítulo anterior (hebreo 1 S 21:1 = KJV 20:42b). Solo se niega el 1:1 de un libro. El versículo tiene que existir ya en `work.db`: si depende de un `versification` nuevo, importar primero y decidir el `join` después |
   | `typo` (`word`, `into`) | Errata de copia de una letra y no hay otra copia buena | Solo si `into` está a 1 letra y la misma Biblia la usa 3+ veces (o bien escrita en el mismo versículo; con guion, cada parte). En chino (sin espacios) busca la subcadena; mínimo 2 caracteres |
   | `restore_chars` (`source`) | La copia perdió caracteres y quedaron `?` o `�` (Unión china de BSS) | Toma de la otra copia solo los caracteres en esas posiciones (reemplazos de igual largo alineados); si algo más difiere, se niega y queda `use_source` |
   | `ligature` (`word`, `into`) | Francés: «oeuvre/coeur» perdió la ligadura (control `ligadura`) | Solo `ou`→`œu` en esa palabra |
   | `dedupe` (`word`) | Palabra copiada dos veces seguidas («katika katika») | Quita una de las dos |
   | `placeholder` | La fuente dejó una nota en lugar del versículo («(ቁጥር 9?)» = «¿versículo 9?», ULB amárica) | Solo si todo el texto es una palabra, el número del versículo y «?»: queda vacío, como un versículo que la edición no trae |
   | `drop_repeat` | El versículo empieza con el anterior copiado entero y un número suelto («…ናት፡፡” 46. ማርያምም…», Lc 1:46 de la ULB amárica) | Quita esa copia y el número; el texto propio queda igual. Se niega si el versículo no empieza con el anterior completo |
   | `override` con `ocr: true` | La misma versión en línea tiene las erratas de OCR de la fuente («0r» por «Or») | Copia la evidencia corrigiendo solo 0→O y 1→l junto a letras |

   Un problema de un capítulo entero (puntuación, alineación) indica el versículo que corrige con `"ref": "PRO 29:6"`.

   **Lo que la validación no ve y hay que buscar** (visto en el nivel 2):
   - **Copias contaminadas**: la Diodati de getBible y BSS tenía capítulos enteros de la Riveduta. Si una copia difiere mucho de otra de la misma versión en capítulos enteros, comparar cada versículo con otra traducción del idioma (la que se parezca más gana).
   - **Capítulos copiados**: la Malayalam 1910 de eBible repetía Tito 1 en Tito 2-3. Buscar textos de versículo idénticos en capítulos distintos (los paralelos reales: Esd 2/Neh 7, Sal 18/2 S 22, Is 36-37/2 R 18-19).
   - **Textos ajenos** («Testing ag live sync»): el control «escritura» los marca en escrituras no latinas.
   - **Placeholders** («_», versículos sin traducir en borradores): una Biblia con versículos sin traducir es incompleta y queda fuera.
   - **Versículos combinados por rango** (`\v 6-7`, muy comunes en Biblica): `scripts/usfm_ranges.py <código>` acepta los vacíos que el propio USFM numera como rango y lista los que no (reconoce ` 26‏-47`, con la marca de dirección del persa/árabe).
   - **Numeración propia de una Biblia** (Diodati, Malayalam 1910): si la detección automática convierte mal un capítulo, `"versification": {"JOB 39": "eng"}` en esa Biblia y luego `join`/`move`/`append_extra` con el texto a la vista; para ubicar el corte, comparar cada versículo con una traducción del mismo idioma que use la numeración de la KJV.
   - **Cientos de versículos corridos** (Gdańska, NBG, Kulish, nivel 3): alinear por programa contra una Biblia de un idioma cercano con numeración KJV (UBG para la Gdańska, la Sinodal rusa para la Kulish), por largo y raíces comunes, proponer `moves`/`joins` por capítulo, revisar a mano cada `join` con el texto a la vista (el alineador se equivoca en los cortes: 2 S 2:5, Is 9:22 en la Kulish) y cargarlos como problemas propios. Antes de aceptar un vacío como «falta en la edición», mirar los versículos vecinos: un número vacío con el texto del siguiente en el anterior es numeración corrida, no un faltante (1 Cr 7:23-24 de la Gdańska).
   - **Notas base copiadas**: si las notas de los pasajes clave se arman a partir de las de otro idioma, quitar antes toda nota que cite el texto o nombre la traducción de origen (una nota yoruba de Ro 5:12 terminó como «matiz» en 14 paquetes). Después de decidir, buscar en `criteria.json` notas con letras o nombres de otro idioma.

   `"want_online": true` en un problema hace que `criteria` busque la misma versión en línea aunque haya otra copia descargada (cuando las dos copias tienen el mismo daño, p. ej. el OCR de la fuente). Un defecto visto en la revisión de versículos clave (no en la validación) se agrega como problema propio con su evidencia y su decisión (clave `W|<biblia>|<control>|<ref>|<motivo>`); `apply` lo aplica y queda en el historial (ejemplo: Isaías 9:6 de la Hindi Contemporary).

   **Agregados entre corchetes** (control `agregado`): la Sinodal marca con corchetes las palabras de los traductores y los agregados de la Septuaginta; algunas ediciones traen además las adiciones griegas de Ester (deuterocanónicas) y notas del editor. Criterio: si la edición canónica de la misma traducción no lo tiene → `use_source` de esa edición; si la canónica también lo trae → `accept` y queda marcado con sus corchetes.

   Para muchas advertencias del mismo tipo que ya revisé (p. ej. 40 "longitud" de una paráfrasis), `bulk: [{"check": "longitud", "bible": "*", "action": "accept", "note": "..."}]` decide las que siguen sin decisión, con esa nota.
4. **Pasajes clave y muestra al azar**: `verdict` = `ok` (dice lo mismo que el original), `matiz` (fiel en lo esencial, con un matiz que hay que conocer: se anota y, si es nuevo, se agrega al healthReport) o `problema` (contradice la doctrina: no se corrige el texto; se rechaza esa Biblia o se consulta al usuario). En `note`, en español, qué dice el versículo y por qué está bien o no. Criterio doctrinal: la Trinidad y la divinidad de Cristo, salvación por gracia mediante la fe sin obras, un solo mediador, sin imágenes, sin purgatorio, la Escritura sola, el canon de 66 libros, la virginidad de María en el nacimiento de Jesús ("hasta que", "primogénito").
5. **`pack.py apply <código>`**: aplica las decisiones a `pack.json` (`criteria_overrides`, `extra_verses_refs`, `include`), se niega entera si alguna rompe las reglas de la tabla, y vuelve a importar, validar y actualizar `criteria.json`. Repetir 3–5 hasta que no queden problemas sin decidir ni errores.
   - Los `override`/`typo`/`split_words` guardan el versículo entero en `criteria_overrides`: si después se agrega una regla de `typography` o `editor_notes`, esos versículos quedarían con el texto viejo. Para rehacerlos, `scripts/reapply.py <código> <biblia>` borra `criteria_overrides` y devuelve esas decisiones a pendientes de aplicar; luego `import`, `validate` y `apply`.

Después de decidir, `pack.py review <código>` vuelve a escribir `review.html` y `report.md` sin tocar la validación ni la aprobación. La hoja muestra arriba solo los problemas actuales (con "PENDIENTE DE DECISIÓN" si falta alguno) y, plegado, el **historial** de los que ya no aparecen (copias descartadas, numeración corregida). La bitácora queda en `criteria.json` y en `review.html`, en la columna **Bitácora de criterio** y en la tabla **Problemas del reporte y cómo se resolvieron**, con enlaces a la evidencia.

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
| ligadura | W | Francés: una palabra sin `œ` que las otras Biblias del paquete escriben con `œ` | `ligature` |
| corrección manual | W | Un `overrides` aplicado | Que el usuario lo vea |

**Correcciones a mano** (`"overrides"` en `pack.json`): no se usan. Toda corrección pasa por el paso de criterio, que exige evidencia de la misma versión y deja la bitácora; los matices doctrinales anotados en healthReport **nunca** se corrigen.

## Reglas

- Un idioma a la vez, y nada se publica (paso 4) sin **0 errores + paso de criterio completo + `approve`**, después de que el usuario vio el resumen de la bitácora y el plan.
- Solo Biblias del tracker y del healthReport (evangélicas, respaldadas por una organización confiable; memoria `biblias-evangelicas`). Si aparece una nueva, primero va al healthReport.
- `work.db` y los reportes quedan en `Modules\languages\<código>\` y los `.obb` en `Modules\cdn\bible\modules\` (fuera de los repos). `module-ids.json` sí va en el repo de la app: hacer commit cuando el usuario lo pida.
- Pruebas sin tocar los datos reales: `BIBLE_VERSIONS_CONFIG=<otro config.json>` en una carpeta con copias (con `app_repo` apuntando a una copia, porque `build` escribe `module-ids.json`).

## Archivos

- `scripts/pack.py`: todo el flujo. La config es `Modules\config.json` (fuera del skill).
- `assets/vrs/*.vrs`: versificaciones de Paratext (de `sil-machine`, licencia MIT de SIL Global, `assets/vrs/LICENSE`).
- `assets/review-verses.json`: los versículos de la revisión humana.
- Respaldo: `D:\Projects\skills\bible-language-pack` (copiar después de cada cambio).
