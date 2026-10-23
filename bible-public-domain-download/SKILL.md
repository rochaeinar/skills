---
name: bible-public-domain-download
description: Descarga para Bible Versions las Biblias de dominio público que solo están en Bible.com (hoy la Xhosa Appleyard 1864/1902 y el Nuevo Testamento en guaraní paraguayo de 1913), capítulo por capítulo, despacio y con caché para retomar, las arma en el formato JSON de getBible que lee bible-language-pack y las registra en bibles-manifest.json y pack.json. Solo baja versiones de una lista cerrada, cada una con la razón por la que es de dominio público; nunca textos con licencia. Úsalo cuando pidan "descargar la Biblia de dominio público de X", "bajar la xhosa 1902 / el guaraní 1913", "agregar una Biblia de dominio público de Bible.com" o "qué Biblias de dominio público hay en Bible.com que no tengamos".
---

# Biblias de dominio público desde Bible.com

Todo pasa por `scripts/download.py` (con `python`). Las rutas se toman de `scripts/config.json` del skill `bible-language-pack` (o de `--config`).

## Qué baja y qué no

Solo las versiones de `PUBLIC_DOMAIN` en `download.py`; cada una lleva el traductor, la editorial y **por qué es de dominio público** (la edad del texto y la muerte del traductor). Cualquier otro id se rechaza. Las Biblias con licencia **nunca** se bajan de Bible.com: se le piden el permiso y el texto a su Sociedad Bíblica (`bible-language-pack`).

| id | Idioma | Biblia | Libros | Por qué es de dominio público |
|---|---|---|---|---|
| 3526 | xh | Xhosa Appleyard 1864/1902 (`XHO1902`) | 66 | Publicada en 1864 y 1902; el traductor, J. W. Appleyard, murió en 1874 |
| 805 | gn | NT en guaraní paraguayo 1913 (`GRN1913`) | 27 | Impreso en 1913; el traductor, J. W. Lindsay, murió en 1946 (vida + 70 en Paraguay; antes de 1929 en EE. UU.). La Sociedad Bíblica Paraguaya lo digitalizó en 2013 |

Revisado el 2026-10-23 con los datos de cada versión en Bible.com (37 versiones de zu, xh, rw, ti, ay, af, tpi, qu, gn: el resto tiene derechos de una Sociedad Bíblica, de City Bible Foundation o de Wycliffe).

**Para agregar otra**: comprobar en los datos de la versión (`https://nodejs.bible.com/api/bible/version/3.1?id=<id>`, `copyright_short` y `copyright_long`) quién la tradujo y cuándo, confirmar que el texto tiene más de 95 años **y** que el traductor murió hace más de 70 (o la regla del país), y que no esté ya en eBible, getBible o CrossWire (en ese caso, bajarla de ahí con `pack.py fetch`). Que sea evangélica y fiel al original (Biblias protestantes de las Sociedades Bíblicas o de misioneros evangélicos; nada católico, mormón ni de los Testigos). Agregarla a `PUBLIC_DOMAIN` con su `reason` y a la tabla de arriba.

## Uso

```bash
python scripts/download.py list            # las versiones, por qué son de dominio público y cuánto falta
python scripts/download.py get 805         # el guaraní: 260 capítulos, unos 18 minutos
python scripts/download.py get 3526        # la xhosa: 1189 capítulos, unos 80 minutos
python scripts/download.py get all --max 200   # en tandas: corta tras 200 pedidos y sigue en la próxima corrida
python scripts/download.py build 3526      # la arma de nuevo desde la caché, sin pedidos
```

- **Despacio**: un pedido cada 4 segundos, uno por capítulo, con el mismo endpoint que usa `pack.py criteria` para verificar. Si Bible.com responde 403 o 429, para enseguida; se vuelve a correr más tarde.
- **Caché**: cada capítulo queda en `packs\_cache\biblecom_pd\<id>\<LIB.C>.json`; una corrida cortada sigue donde quedó y nunca pide dos veces el mismo capítulo. Correrla en segundo plano (con `nohup` en Git Bash) si son muchos capítulos.
- **Resultado**: `BibleVersionsSelected\<carpeta del idioma>\biblecom_<id>.json`, en el formato de getBible (`books[nr, chapters[verses[chapter, verse, text]]]`, libros 1-66 en el orden de la app). Del HTML toma solo el texto de los versículos: deja fuera los títulos de sección, las notas y las referencias; un versículo partido en dos párrafos se une; el título de un Salmo queda como versículo 0 (`pack.py import` lo une al 1); un versículo combinado (`GEN.1.1+GEN.1.2`) queda en el primero.
- **Registro**: lo agrega a `bibles-manifest.json` (fuente, licencia «Public domain» con la razón, sha256) y, si el idioma ya tiene `pack.json`, ahí con `include: false`, como hace `pack.py fetch`. Si el idioma todavía no tiene paquete (la xhosa), `pack.py init xh` la ofrece.

## Después

Sigue el flujo normal de `bible-language-pack`: `init` o editar `pack.json` (`include: true`, `abbreviation`, `description`, `attribution` con el traductor y el año, `default_bible`), `import`, `validate`, el paso de criterio pastoral, `approve` y `build`. Al ser de dominio público, **no** lleva `licence_review` y puede usarse en todos los países.

Lo que hay que mirar en estas dos:
- **Xhosa 1902**: ortografía antigua (anterior a la reforma de los años 50: «Tixo», «pakama», letras con punto como «ṙ»). No se moderniza: es el texto de esa edición. Avisar al usuario de que suena antigua, como la Reina-Valera 1602 en español.
- **Guaraní 1913**: solo el Nuevo Testamento. Puede ir junto con la Biblia mbyá que ya tiene el paquete `gn` (que es otra variante); decidir con el usuario cuál es la principal.

## Archivos

- `scripts/download.py`: el script (lista cerrada `PUBLIC_DOMAIN`, descarga con caché, armado y registro).
- Respaldo del skill: `D:\Projects\skills\bible-public-domain-download`.
