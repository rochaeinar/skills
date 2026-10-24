---
name: bible-devotional-translate
description: Traduce la reflexión diaria de Bible Versions (coffee_es.dev, 464 reflexiones con su versículo) a otro idioma - siempre desde el español, que tiene la intención original, con el inglés solo como apoyo para las dudas - y la deja lista en el paquete del idioma (coffee_<idioma>.dev con su Id registrado, pack.json, languages.json) o en los paquetes del español y del inglés. Es incremental - si el español cambia o se le agregan reflexiones, solo traduce esas filas en cada idioma. Úsalo cuando pidan "traducir la reflexión / el coffee / el devocional al idioma X", "reflexión diaria en X", "agregué reflexiones al español, actualiza los idiomas", "corregí el coffee_es, propaga los cambios" o "rearma el paquete del español / inglés con el coffee nuevo".
---

# Reflexión diaria en otros idiomas

**Paso 3 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md`. Viene después de `bible-language-pack` (paso 2: la Biblia del idioma en `modules\`, para los términos); sigue `pack.py build <idioma>` (paso 2 otra vez, para meter la reflexión en el `.obb`) y `bible-language-ship` (paso 4). **No arma ni sube paquetes.**

Todo pasa por `scripts/coffee.py` (con `python`). Config: `Modules\config.json` (`SETUP.md`).

- **Original**: `Modules\common\es\coffee_es.dev` (lo comparten los paquetes es y es-lite), tabla `DAILY` (`Id`, `Book`, `Chapter`, `Verse`, `VerseEnd`, `Comments`, `rowid`) y `Details` (una fila: `Id` 45, `Language` es). Es la fuente de verdad: el texto, las referencias y la cantidad de filas salen de ahí.
- **Trabajo por idioma**: `Modules\languages\<idioma>\devotional\`: `state.json` (cada traducción con el hash del español que tradujo), `glossary.md` (términos y decisiones), `batches\` (tandas), `report.md` (validación), `backups\`.
- **Salida**:
  - Un idioma de `Modules\languages\<idioma>\` → `modules\coffee_<código>.dev` (Id nuevo en `cdn/bible/module-ids.json` del repo de la app); en `contents` de su `pack.json` reemplaza a `common/en coffee_en.dev` (es lo único de `pack.json` que toca este skill). `pack.py build` del skill `bible-language-pack` lo mete en el `.obb`.
  - Inglés (`en`) → `Modules\common\en\coffee_en.dev` (Id 43). Español: lo edita el usuario o el skill de corrección. Los paquetes en, es y es-lite se rearman con `pack.py build en / es / es-lite` (bible-language-pack).
- **Cómo lo usa la app**: `ModuleInitializer` registra todo `coffee*.dev` por su fila de `Details`; el idioma muestra el módulo cuyo Id está en `dailyImage` de `app/src/main/assets/languages.json` (hoy 43, el inglés, en todos los idiomas nuevos). El español (45) y el inglés (43) están fijos en `LanguageManager.java`.

## Flujo para un idioma

1. `coffee.py check-source`: revisa el original (ids, referencias contra la RV1960, textos vacíos, espacios, duplicados). Con errores no se traduce: se corrigen primero en `coffee_es.dev`.
2. `coffee.py prepare <idioma> [--size 40]`: crea las tandas `batches\todo-NNN.json` solo con lo pendiente (filas nuevas o cuyo español cambió) y el `glossary.md` si no existe. Cada elemento trae `id`, `ref`, `es` (el original), `en` (apoyo), `verse_es` (RV1960), `verse` (el versículo en la Biblia principal del paquete), `previous` (la traducción anterior si el español cambió) y `es_sha` (no se toca).
3. **Antes de la primera tanda, llenar `glossary.md`** mirando los `verse` de varias tandas y la Biblia del paquete: cómo dice esa Biblia Dios, Señor, Jesucristo, Espíritu Santo, gracia, fe, Palabra, oración, bendición, pecado, salvación; el tratamiento del lector; mayúsculas de los pronombres de Dios; comillas. Ver `assets/language-notes.md`.
   - **Investigar en la web los términos dudosos** (WebSearch/WebFetch), antes de fijarlos en el glosario o cuando una duda aparezca al traducir o en la revisión. Es obligatorio si: la Biblia del paquete es antigua o poco usada (de dominio público: Terjemahan Lama, Kulish, Judson, Synodal…), hay dos términos en uso para una idea clave (gracia: *anugerah* / *kasih karunia*), el idioma tiene pocos recursos, o un término parece católico, de otra confesión o arcaico.
   - **Criterio evangélico, como la RV1960 en español**: identificar la Biblia protestante de referencia del idioma (la que leen y citan hoy las iglesias evangélicas, p. ej. la Terjemahan Baru de LAI en indonesio, la Ogienko en ucraniano, el 和合本 en chino) y mirar cómo traduce los versículos clave en un comparador de versiones (alkitab.sabda.org, bible.com, biblegateway.com, biblehub.com/multi). Gana el término de esa Biblia y de la predicación evangélica actual si es doctrinalmente equivalente; si no, el de la Biblia del paquete. Nunca uno que cambie la doctrina.
   - **Bitácora**: anotar la decisión, las alternativas, qué Biblias usa cada una y las URL de las fuentes. Si el cambio llega cuando el idioma ya está traducido: listar las filas afectadas (comparando con el español), `prepare <idioma> --ids …`, corregir solo ese término, `apply`, `validate`, `build`.
4. **Traducir cada tanda** (reglas abajo) y escribir `batches\done-NNN.json` con `{"<id>": "texto traducido"}`. Leer la tanda entera antes de escribir: las reflexiones repetidas (97/419, 295/296, 300/301, 386/387, 398/399) van idénticas.
5. `coffee.py apply <idioma>`: guarda las tandas en `state.json`. Repetir 2-5 hasta que no queden pendientes.
6. `coffee.py validate <idioma>` → `report.md`. Errores (sin traducir, español cambiado, marcas, otra escritura) bloquean el paso siguiente; las advertencias (largo raro, número o emoji que falta, atribución, comillas, palabras en inglés o español, repetidas distintas) se revisan una por una y se corrigen con otra tanda o se justifican en la bitácora del glosario.
7. `coffee.py build <idioma>`: escribe el módulo (mismo esquema que el original; `Details` con el Id y el código del idioma), lo registra y ajusta `pack.json`.
8. `pack.py build <idioma>` (skill `bible-language-pack`; necesita el paquete aprobado y `work.db` sin cambios) y luego `coffee.py integrate <idioma>`: pone `dailyImage` (el Id nuevo) y `sizeInBytes` en `languages.json`, solo esas dos líneas. Si el idioma todavía no está en la app (ar, fa, ja, my), queda listo en el paquete y `bible-language-ship` usa ese Id al integrarlo.
9. **Publicar, con permiso explícito del usuario**: `ship.py cdn <idioma>` (bible-language-ship: sube el `.obb` y publica el manifiesto), y una versión nueva de la app (`languages.json` va dentro del APK; skill `android-release`). Commit en `master` de la app con `languages.json` y `module-ids.json` cuando el usuario lo pida.

Quien ya bajó el idioma no recibe el módulo nuevo: la app descarga cada paquete una vez. Le llega a quien lo baje después de publicar.

## Cuando el español cambia o crece

- **Filas nuevas**: agregarlas al final de `coffee_es.dev` con `Id` (y `rowid`) siguientes, su referencia y el texto. **Correcciones**: editar `Comments` o la referencia. Luego `check-source`.
- El español va también en el paquete Lite: los dos usan la misma copia, `common\es\coffee_es.dev`. `pack.py build es` y `pack.py build es-lite` arman sus `.obb` en `Modules\cdn\bible\modules\` con la regla de versiones (se reemplaza la versión que aún no salió en un release de la app).
- **Cada idioma**: `status` muestra los pendientes; `prepare` trae solo las filas nuevas o cambiadas (las cambiadas con `previous`: ajustar esa traducción a lo que cambió, sin retraducir lo demás). Después `apply`, `validate`, `build`, y `pack.py build en` para el inglés o `pack.py build <idioma>` + `integrate` para los paquetes.
- Un cambio solo de referencia (sin texto) no deja la fila pendiente: `build` copia las referencias del español siempre.
- Para tomar como vigente un módulo que ya existe (el inglés actual, una traducción hecha afuera): `coffee.py import <idioma> <archivo.dev>` (con `--only-missing` para no pisar lo ya traducido). Solo si se revisó contra el español actual.

## Cómo traducir (reglas)

- **El español manda.** Traducir lo que dice el español, con su intención pastoral y su tono cálido y directo. El inglés (`en`) es una traducción automática corregida: sirve para resolver una duda (una frase ambigua, un juego de palabras) y para ver qué entendió otro traductor, nunca como fuente. Si el inglés y el español discrepan, gana el español.
- **No agregar, quitar ni suavizar ideas.** Una oración por cada oración, salvo que la gramática del idioma pida unir o partir. Mantener las exhortaciones (¡Confía!, ¡No te rindas!), las preguntas al lector y los paralelismos (*"El que no vive para servir, no sirve para vivir"*: buscar un juego equivalente; si no existe, traducir el sentido y anotarlo en la bitácora).
- **Errores del original**: si el español tiene un error de gramática evidente (*"La dificultades"*, *"tampoco no merecías"*), traducir lo que quiso decir. Si el sentido es dudoso, mirar el inglés y anotarlo en la bitácora; no inventar.
- **Doctrina**: es una reflexión evangélica; usar el vocabulario de la Biblia del paquete y el de las iglesias evangélicas del idioma (nada de términos católicos o de otras confesiones cuando haya alternativa: ver la memoria `biblias-evangelicas`). Las citas implícitas de la Biblia (*"todo ayuda a bien"*, *"echa fuera el temor"*, *"más que vencedores"*) van con las palabras de esa Biblia (`verse`).
- **Nombres y atribuciones**: Paul Tripp, C.S. Lewis, John Newton, Spurgeon, Corrie ten Boom, Oswald Chambers, Elisabeth Elliot, R. C. Sproul, Kierkegaard: en alfabeto latino se escriben igual; en otras escrituras, con la transliteración usual del idioma. Job, Noé, Belén, Calvario: como en la Biblia del paquete.
- **Forma**: un solo párrafo, sin saltos de línea, sin markdown ni comillas tipográficas mezcladas; conservar números (365), el emoji 📖 y los signos del idioma (comillas «» en francés, „“ en alemán, 「」 en japonés; ¡ ¿ solo en español). Mayúsculas en los pronombres de Dios solo si el idioma lo acostumbra en textos cristianos (inglés He/His, español Él/Su; alemán y francés no).
- **Registro**: el del devocional en ese idioma, constante en todas las reflexiones (tú/du/tu; en japonés です・ます; en coreano 해요/합니다 según el glosario).
- **Calidad por idioma**: en los idiomas con pocos recursos (Twi, Oromo, Luganda, Lingala, Shona, Tok Pisin, Quechua, Guaraní) avisar al usuario antes de empezar que la traducción necesita revisión de un hablante nativo y proponer dejar el inglés (o el español en quechua y guaraní, que tienen la interfaz en español). No publicar esos idiomas sin su visto bueno.

## Estado y reportes

- `coffee.py status`: traducidas, pendientes, módulo y `dailyImage` de cada idioma.
- `report.md` de cada idioma y la **bitácora** de `glossary.md` (qué se decidió y por qué, qué revisar con un nativo) son lo que se le muestra al usuario al terminar.
- Nunca editar `state.json` a mano. Para corregir traducciones ya hechas (una advertencia del reporte, un comentario de un hablante nativo): `coffee.py prepare <idioma> --ids 12,40` las trae con su texto en `previous`; se corrigen en `done-NNN.json` y se sigue con `apply`.
