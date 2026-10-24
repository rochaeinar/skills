---
name: bible-download
description: Paso 1 de 5 del flujo de idiomas de Bible Versions (Modules/README.md) - descarga Biblias de Bible.com capítulo por capítulo (despacio y con caché para retomar) o de getBible en un solo pedido, las deja en Modules/languages/<idioma>/sources en el formato JSON de getBible que lee bible-language-pack y las registra en languages/manifest.json y pack.json. No elige, no valida ni arma paquetes. Úsalo cuando pidan "descargar la Biblia", "bajar la xhosa 1902 / el guaraní 1913", "agregar una Biblia de Bible.com o getBible" o "qué Biblias hay en Bible.com que no tengamos".
---

# Biblias desde Bible.com

**Paso 1 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md`. Sigue **bible-language-pack** (paso 2: `pack.py init <idioma>` o elegir la Biblia en `pack.json`). Solo descarga y registra: no elige, no valida ni arma paquetes.

Todo pasa por `scripts/download.py` (con `python`). Config: `Modules\config.json` (otro con la variable `BIBLE_VERSIONS_CONFIG`). Con `--output-dir` todo queda aislado en esa carpeta (`_cache\biblecom_pd`, `bibles\<código>`, su propio `bibles-manifest.json`), sin tocar `Modules`: solo para pruebas.

## Qué baja

Cualquier biblia, cada una lleva el traductor, la editorial.

| id | Idioma | Biblia | Libros 
|---|---|---|---|---|
| 3526 | xh | Xhosa Appleyard 1864/1902 (`XHO1902`) | 66 
| 805 | gn | NT en guaraní paraguayo 1913 (`GRN1913`) | 27 

Revisado el 2026-10-23 con los datos de cada versión en Bible.com (37 versiones de zu, xh, rw, ti, ay, af, tpi, qu, gn: el resto tiene derechos de una Sociedad Bíblica, de City Bible Foundation o de Wycliffe).

**Para agregar otra**: comprobar en los datos de la versión (`https://nodejs.bible.com/api/bible/version/3.1?id=<id>`) quién la tradujo y cuándo, y que no esté ya en eBible, getBible o CrossWire (en ese caso, bajarla de ahí: getBible con `download.py getbible <abbr> --lang <idioma>`). Que sea evangélica y fiel al original (Biblias protestantes de las Sociedades Bíblicas o de misioneros evangélicos; nada católico, mormón ni de los Testigos).

## Uso

# Listar versiones descargadas en caché y el progreso de capítulos
python scripts/download.py list

# Descargar una versión completa por ID (reanuda desde la caché)
python scripts/download.py get 805
python scripts/download.py get 3526

# Descargar en tandas de hasta 200 capítulos por ejecución
python scripts/download.py get all --max 200

# Reconstruir el JSON desde la caché, sin realizar solicitudes
python scripts/download.py build 3526

# Descargar un libro individual (código USFM)
python scripts/download.py get-book 805 GEN
python scripts/download.py get-book 3526 JHN

# Limitar la descarga de un libro a 10 capítulos en esta ejecución
python scripts/download.py get-book 805 GEN --max 10

# Código del tracker distinto al de Bible.com (la tigriña viene como "tir", la aimara como "ayr")
python scripts/download.py build 2998 --lang ti --language-code ti

# Una traducción entera de getBible en un solo pedido (si ya está en sources\, no pide nada)
python scripts/download.py getbible synodal --lang ru

# Prueba aislada en otra carpeta (no toca Modules)
python scripts/download.py --output-dir "D:\bible-test" get 805
python scripts/download.py --output-dir "D:\bible-test" get-book 805 GEN
python scripts/download.py --output-dir "D:\bible-test" build 805

- **Despacio**: un pedido cada 0.2 segundos, uno por capítulo, con el mismo endpoint que usa `pack.py criteria` para verificar. Si Bible.com responde 403 o 429, para enseguida; se vuelve a correr más tarde.
- **Caché**: cada capítulo queda en `Modules\_cache\biblecom_pd\<id>\<LIB.C>.json`; una corrida cortada sigue donde quedó y nunca pide dos veces el mismo capítulo (volver a correr `get` de una versión completa no hace ningún pedido). Correrla en segundo plano (con `nohup` en Git Bash) si son muchos capítulos.
- **Resultado**: `Modules\languages\<idioma>\sources\biblecom_<id>.json` (`<idioma>` = `--lang`, el código del tracker; `--folder` fija otra carpeta relativa a `languages\`), en el formato de getBible (`books[nr, chapters[verses[chapter, verse, text]]]`, libros 1-66 en el orden de la app). Del HTML toma solo el texto de los versículos: deja fuera los títulos de sección, las notas y las referencias; un versículo partido en dos párrafos se une; el título de un Salmo queda como versículo 0 (`pack.py import` lo une al 1); un versículo combinado (`GEN.1.1+GEN.1.2`) queda en el primero.
- **Registro**: lo agrega a `Modules\languages\manifest.json` (fuente, editorial, sha256) y, si el idioma ya tiene `pack.json`, ahí con `include: false`. Si el idioma todavía no tiene paquete (la xhosa), `pack.py init xh` la ofrece.

## Después

Paso 2, el skill `bible-language-pack` (este skill no lo ejecuta): `init` o editar `pack.json` (`include: true`, `abbreviation`, `description`, `attribution` con el traductor y el año, `default_bible`), `import`, `validate`, el paso de criterio pastoral, `approve` y `build`.

Lo que hay que mirar en estas dos:
- **Xhosa 1902**: ortografía antigua (anterior a la reforma de los años 50: «Tixo», «pakama», letras con punto como «ṙ»). No se moderniza: es el texto de esa edición. Avisar al usuario de que suena antigua, como la Reina-Valera 1602 en español.
- **Guaraní 1913**: solo el Nuevo Testamento. Puede ir junto con la Biblia mbyá que ya tiene el paquete `gn` (que es otra variante); decidir con el usuario cuál es la principal.

## Archivos

- `scripts/download.py`: el script (descarga con caché, armado y registro).
- Respaldo del skill: `D:\Projects\skills\bible-download`.
