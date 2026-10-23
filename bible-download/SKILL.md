---
name: bible-download
description: Descarga para modulos de en Bible.com capítulo por capítulo, despacio y con caché para retomar, las arma en el formato JSON de getBible que lee bible-language-pack y las registra en bibles-manifest.json y pack.json. Úsalo cuando pidan "descargar la Biblia", "bajar la xhosa 1902 / el guaraní 1913", "agregar una Biblia de Bible.com" o "qué Biblias hay en Bible.com que no tengamos".
---

# Biblias desde Bible.com

Todo pasa por `scripts/download.py` (con `python`). Las rutas se toman de `scripts/config.json` del skill `bible-language-pack` (o de `--config`).

## Qué baja

Cualquier biblia, cada una lleva el traductor, la editorial.

| id | Idioma | Biblia | Libros 
|---|---|---|---|---|
| 3526 | xh | Xhosa Appleyard 1864/1902 (`XHO1902`) | 66 
| 805 | gn | NT en guaraní paraguayo 1913 (`GRN1913`) | 27 

Revisado el 2026-10-23 con los datos de cada versión en Bible.com (37 versiones de zu, xh, rw, ti, ay, af, tpi, qu, gn: el resto tiene derechos de una Sociedad Bíblica, de City Bible Foundation o de Wycliffe).

**Para agregar otra**: comprobar en los datos de la versión (`https://nodejs.bible.com/api/bible/version/3.1?id=<id>`) quién la tradujo y cuándo, y que no esté ya en eBible, getBible o CrossWire (en ese caso, bajarla de ahí con `pack.py fetch`). Que sea evangélica y fiel al original (Biblias protestantes de las Sociedades Bíblicas o de misioneros evangélicos; nada católico, mormón ni de los Testigos).

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

# Elegir explícitamente el directorio de salida
python scripts/download.py --output-dir "D:\bible-test" get 805
python scripts/download.py --output-dir "D:\bible-test" get-book 805 GEN
python scripts/download.py --output-dir "D:\bible-test" build 805

- **Despacio**: un pedido cada 0.2 segundos, uno por capítulo, con el mismo endpoint que usa `pack.py criteria` para verificar. Si Bible.com responde 403 o 429, para enseguida; se vuelve a correr más tarde.
- **Caché**: cada capítulo queda en `packs\_cache\biblecom_pd\<id>\<LIB.C>.json`; una corrida cortada sigue donde quedó y nunca pide dos veces el mismo capítulo. Correrla en segundo plano (con `nohup` en Git Bash) si son muchos capítulos.
- **Resultado**: `BibleVersionsSelected\<carpeta del idioma>\biblecom_<id>.json`, en el formato de getBible (`books[nr, chapters[verses[chapter, verse, text]]]`, libros 1-66 en el orden de la app). Del HTML toma solo el texto de los versículos: deja fuera los títulos de sección, las notas y las referencias; un versículo partido en dos párrafos se une; el título de un Salmo queda como versículo 0 (`pack.py import` lo une al 1); un versículo combinado (`GEN.1.1+GEN.1.2`) queda en el primero.
- **Registro**: lo agrega a `bibles-manifest.json` (fuente, licencia, sha256) y, si el idioma ya tiene `pack.json`, ahí con `include: false`, como hace `pack.py fetch`. Si el idioma todavía no tiene paquete (la xhosa), `pack.py init xh` la ofrece.

## Después

Sigue el flujo normal de `bible-language-pack`: `init` o editar `pack.json` (`include: true`, `abbreviation`, `description`, `attribution` con el traductor y el año, `default_bible`), `import`, `validate`, el paso de criterio pastoral, `approve` y `build`.

Lo que hay que mirar en estas dos:
- **Xhosa 1902**: ortografía antigua (anterior a la reforma de los años 50: «Tixo», «pakama», letras con punto como «ṙ»). No se moderniza: es el texto de esa edición. Avisar al usuario de que suena antigua, como la Reina-Valera 1602 en español.
- **Guaraní 1913**: solo el Nuevo Testamento. Puede ir junto con la Biblia mbyá que ya tiene el paquete `gn` (que es otra variante); decidir con el usuario cuál es la principal.

## Archivos

- `scripts/download.py`: el script (descarga con caché, armado y registro).
- Respaldo del skill: `D:\Projects\skills\bible-download`.
