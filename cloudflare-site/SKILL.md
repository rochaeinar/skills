---
name: cloudflare-site
description: Crea y publica la web oficial de una app (landing estática muy profesional, un subdominio por app) en Cloudflare Pages, desde un monorepo de Astro con muchas apps y varias cuentas de Cloudflare. Analiza la app a fondo (código, ficha de Play, video), busca imágenes y videos en la carpeta externa de la app, guía la conexión del teléfono para capturas, muestra mockups en Claude Design antes de programar, compila con controles de SEO, accesibilidad y tamaño, y publica con wrangler (vista previa o producción) y dominio propio. Además integra la app con su web: redacta desde el análisis del código la política de privacidad, los términos y las licencias de código abierto, los muestra en Markdown en el Acerca de de la app (lo crea si no existe) junto al enlace al sitio, publica la privacidad en la web y registra su URL en la carpeta de Play de la app. Úsalo cuando pidan "crear la web / landing / página de la app", "publicar la web en Cloudflare", "actualizar la web de <app>", "subdominio para la app", "política de privacidad web", "términos y condiciones", "licencias de código abierto en la app", "Acerca de con el sitio" o "deploy de los sitios".
---

# Webs de apps en Cloudflare Pages

**Antes del primer uso en una PC, con una cuenta de Cloudflare nueva o un dominio nuevo: `SETUP.md`.**

Todo pasa por `scripts/web.py` (con `python`). El monorepo (en esta PC: el de `config.json` del skill, p. ej. `D:/Projects/websites`) tiene un sitio Astro por app en `sites/<slug>/`, descrito por `site.json`:

| Campo | Qué es |
|---|---|
| `profile` | Cuenta de Cloudflare (perfil de `accounts.json`; su token: `CloudflarePages@<perfil>` en el Administrador de credenciales) |
| `project` | Proyecto de Pages (único en esa cuenta; URL `<project>.pages.dev`) |
| `domain` | Subdominio público, en una zona de esa misma cuenta |
| `locales`, `default_locale` | Idiomas (`en`, `es`…); el idioma por defecto va sin prefijo, los demás en `/<lang>/` |
| `play.package`, `youtube.<lang>`, `category`, `theme_color`, `analytics_token` | Datos de la app para la insignia, el video, los datos estructurados y la analítica |
| `app_project`, `assets_dir`, `play_dir` | Fuera del repo: el proyecto de la app, la carpeta de imágenes/videos (`D:/Documents/Apps/<App>/Images`) y la de Google Play (`.../<App>/play`, la misma de `play-console`) |

Comandos: `init`, `auth`, `new`, `assets`, `import`, `capture`, `licenses`, `legal`, `build`, `qa`, `preview`, `deploy`, `domain`, `status` (ver la cabecera de `web.py`).

**La web no se entrega sola:** la app enlaza su sitio desde Acerca de y muestra la privacidad, los términos y las licencias que la web publica; Google Play recibe la URL de privacidad. Guía completa: `references/app-integration.md` (pasos 1b, 5b y 7).

## Flujo para una app nueva

### 0. Crear el sitio
`web.py new <slug> --profile <cuenta> --domain <sub.dominio> --package <applicationId> --name "<App>" --app-project <carpeta> --assets <carpeta de imágenes>`, luego `npm install` en el monorepo. **Pedir al usuario** las rutas del proyecto de la app y de su carpeta de imágenes (no están en el repo) y el acceso a ellas si no están en el directorio de trabajo. Cada app tiene su carpeta en `D:/Documents/Apps/<App>/` (`Images/`, `play/`…), nunca suelta en Documents. `play_dir` sale de `play-console` (si ya registró el paquete) o es `<carpeta de la app>/play`.

### 1. Análisis exhaustivo de la app (no superficial)
Hacerlo directamente (sin subagentes, salvo que el usuario los pida) y escribirlo en `sites/<slug>/content/analysis.md` (plantilla incluida). Recorrer, para una app Android:
- `AndroidManifest.xml`: actividades, permisos, *deep links*, servicios (audio, sincronización), widgets.
- **Cada pantalla**: actividades, fragments, menús (`res/menu`), navegación, diálogos, ajustes (`res/xml` de preferencias y su código), estados vacíos, funciones ocultas tras gestos o largas pulsaciones.
- `res/values*/strings.xml` de **cada idioma**: los nombres reales de las funciones y el tono; qué idiomas soporta.
- Datos e integraciones: base de datos y modelos, sincronización (Drive…), analítica, anuncios (AdMob), compras, notificaciones, red/CDN.
- Límites reales (p. ej. "hasta 4 versiones en paralelo en teléfono"): **toda afirmación de la web se verifica en el código** y se anota con `archivo:línea`.
- Lo ya escrito: `CLAUDE.md` y `plans/` del repo, la ficha de Play (`play-console pull`: `listing/<lang>/full.txt`), notas de versión, guion del video promocional (`app-promo-video`: `video.json`), `git log` de las funciones recientes.
- Identidad visual: `colors.xml`/temas (claro y oscuro), tipografías, logo y su SVG.
Resultado: inventario de funciones con beneficio, evidencia y prioridad; diferenciadores; datos para la política de privacidad; palabras clave. Presentar al usuario el resumen y las 5-8 funciones elegidas para la web.

### 1b. Documentos de la app (privacidad, términos, licencias)
Según `references/app-integration.md` §1-2: qué tiene la app (pila, Acerca de, navegación, tema, idiomas) y el análisis de datos (manifiesto final, red, SDK, almacenamiento, respaldo, registros, edad). `web.py licenses <slug>` hace el inventario de las dependencias del release con su licencia (`content/licenses-inventory.md`). Con eso se redactan `app/src/main/assets/legal/{privacy,terms,licenses}.md` **solo en inglés (nunca se traducen, ni en la app ni en la web)** desde `templates/android/legal/`: **cada frase verificada en el código**, nada copiado del ejemplo. Son documentos importantes: entregárselos al usuario para que los revise (no es asesoría legal).

### 2. Recursos existentes
`web.py assets <slug>` hace el inventario de `assets_dir` (`content/assets-inventory.md`: tamaño y duración). Mirar con Read las candidatas (capturas por idioma, imagen destacada, logo, videos promocionales ya hechos y sus clips en `promo-video/clips`). Las capturas deben ser reales, del idioma de cada página y sin defectos (textos rotos, datos personales, barra de estado sucia).

### 3. Capturas del teléfono (si faltan)
Pedir al usuario que conecte el teléfono y guiarlo: USB, desbloqueado, **Opciones de desarrollador → Depuración USB**, aceptar "¿Permitir depuración USB?"; comprobar con `adb devices`. Luego:
- Pantalla: `web.py capture <slug> shot <nombre>`; video corto: `web.py capture <slug> record <nombre> --seconds 15` (el usuario hace la acción mientras graba). Se guardan en `<assets_dir>/web-captures/`.
- Si el repo de la app tiene flujos Maestro (`.maestro/promo/`), reutilizarlos para escenas repetibles.
- Respaldar y restaurar los ajustes del teléfono y de la app que se toquen (reglas del `CLAUDE.md` de la app).
- Revisar cada captura con Read y luego `web.py import <slug> <archivo> --trim --to screens/<lang> --name <función>-<light|dark>`: `--trim` quita la barra de estado (franja negra superior) y la de navegación (48 dp abajo). Las imágenes van a `src/assets/` (Astro genera AVIF/WebP en el build); los videos se recomprimen sin sonido a ≤1080 px con póster en `public/media/` (límite de Pages: 25 MiB por archivo). Videos largos con sonido: el de YouTube (`youtube.<lang>`), con su miniatura propia en `src/assets/video/poster-<lang>.jpg` (la de `app-promo-video`, `upload/<video>/thumbnail.jpg`: la `maxresdefault` de YouTube no existe en todos los videos y sale gris).
- **Una captura por función, idioma y tema**: `src/assets/screens/<lang>/<función>-light.jpg` y `-dark.jpg`. `<Shot name lang>` (`src/components/Shot.astro`) muestra la del tema de la página; sin una de las dos usa la otra; sin ese idioma usa la del idioma de respaldo y el build lo avisa (`WARNING [Shot]`): eso queda pendiente de captura. Tablet: `src/assets/tablet/<lang>/<función>-light|dark.jpg` (horizontal, sin barras) y `<Shot device="tablet">` (marco de tablet; `size="sm"` para tarjetas). Los idiomas que la app no tiene usan las capturas en inglés.

### 4. Mockups en Claude Design (antes de programar)
Con la herramienta Artifact: `action: "quickstart"`, `intent: "design"`, y seguir sus instrucciones para crear el diseño. Mockups de la landing en **escritorio y teléfono**, con las capturas y textos reales del análisis, acordes al tema de la app (paleta y tipografía de la app, tono). Nivel: web de producto de primera línea (jerarquía clara, mucho aire, tipografía grande, profundidad sutil, animaciones discretas, claro y oscuro). Proponer 2-3 direcciones si el usuario no tiene una idea, iterar con sus comentarios y **no implementar hasta que apruebe una**.

### 5. Implementar en Astro
- `src/styles/theme.css`: los tokens del mockup aprobado, en **claro y oscuro**: el oscuro se aplica si el sistema está en oscuro y el visitante no eligió claro, o si eligió oscuro (`html[data-theme]`, botón `ThemeToggle` + `ThemeScript` en el `<head>`, ya en el `Layout`). Fuentes de `@fontsource` alojadas en el sitio; precargar en el `Layout` las dos principales (subconjunto latino) para que el texto no salte.
- `src/components/Home.astro` es solo un punto de partida: rehacer las secciones como en el mockup. Textos solo en `src/i18n/<lang>.json` (traducciones naturales, no literales). Íconos: `@lucide/astro`. Componentes compartidos en `packages/ui/src/` (SEO, insignia oficial de Google Play, YouTube liviano, analítica, tema, sugerencia de idioma, selector de idioma `LangPicker`): mejorarlos allí si sirve a todas las apps.
- **Idiomas:** `site.json` `locales` + un `src/i18n/<lang>.json` con las mismas claves que `en.json`; las páginas de `src/pages/[lang]/` se generan solas, con `hreflang`, sitemap y `dir="rtl"` para árabe, persa, hebreo y urdu. Nunca redirigir por idioma: `LangSuggest` muestra un aviso según el navegador. El header usa `LangPicker` (botón con el idioma actual → diálogo con buscador; los idiomas del navegador primero y el resto en el orden de `locales`, que es la prioridad del sitio; textos en `langPicker` de cada `src/i18n/<lang>.json`): aguanta decenas de idiomas. Si la web está en idiomas que la app no tiene, decirlo claro (p. ej. "la app está en inglés y español") y traducir con revisión de un hablante nativo en los idiomas de menos recursos.
- `public/og.png` (1200×630, derivada de la imagen destacada de Play; `og-<lang>.png` por idioma), `public/favicon.svg` y `src/assets/logo.svg` desde el logo, `public/apple-touch-icon.png` (180×180).
- **Documentos legales** (`/privacy/`, obligatoria para Play, y `/terms/`; `/credits/` solo si la app tiene créditos de imágenes): **nunca se escriben en la web**. `web.py legal <slug>` copia los de la app (`assets/legal/`, paso 1b) a `src/legal/<doc>.md`, quita las plantillas que no se usan y registra los enlaces en Play (`Legal.astro` muestra el mismo texto en inglés en todos los idiomas del sitio; solo el título y el enlace de volver se traducen). Si la app usa AdMob: `public/app-ads.txt` con la línea que da AdMob (debe estar en el dominio de "sitio web del desarrollador" de la ficha de Play: verificarlo en la ayuda de AdMob al configurarlo).

### 5b. Acerca de en la app
Según `references/app-integration.md` §3, con las plantillas de `templates/android/` (Compose o Views, Kotlin; adaptadas a la arquitectura, los componentes y el tema de la app): **enlace al sitio** (abre el navegador) y la tarjeta "Legal e información" con Política de privacidad, Términos y condiciones y Licencias de terceros, cada uno en Markdown con Markwon 4.6.2. Si la app ya tiene Acerca de se completa (y se reemplazan los diálogos legales viejos); si no, se crea y se enlaza desde Ajustes o el menú. Las etiquetas se traducen a todos los idiomas de la app, los documentos no; `about_web_url` y `privacy_policy_url` con el dominio del sitio. Compilar, instalar y revisar en el dispositivo (claro/oscuro, idioma sin documento, horizontal, enlaces) y agregar un flujo de humo si la app tiene Maestro. Después, `web.py legal <slug>` debe terminar en OK salvo las respuestas de `play/app-content.md`, que se completan desde el análisis (seguridad de los datos, anuncios, edad, permisos a declarar). Commit en el repo de la app solo si el usuario lo pide.

### 5c. Detalles de la web
- Sin JavaScript salvo lo imprescindible; imágenes siempre con `<Picture>`/`<Image>` de `astro:assets` y `alt`. El CSS va dentro de cada página (`inlineStylesheets: "always"`).

### 6. Build y control de calidad
- `web.py build <slug>`: compila y falla si hay archivos >25 MiB, más de 20.000 archivos, páginas sin `lang`/`title`/descripción/`og:image`/canonical, imágenes sin `alt`, enlaces internos rotos o texto `TODO`/`{{…}}`.
- `web.py qa <slug> [--pages /,/es/] [--theme light|dark|both] [--lighthouse]`: capturas de cada página en escritorio (1440 px) y teléfono (390 px), en claro y oscuro, en `content/qa/` → **revisarlas con Read** (cortes, desbordes, contraste, idioma, capturas del idioma correcto) y compararlas con el mockup. Lighthouse en móvil, con los tiempos y lo que falta mejorar: apuntar a 95+ en accesibilidad, buenas prácticas y SEO. El rendimiento local sale más bajo que en Cloudflare (el servidor local no comprime ni cachea).

### 7. Publicar
1. `web.py deploy <slug>`: vista previa en `https://preview.<project>.pages.dev` (crea el proyecto de Pages si no existe). Darle el enlace al usuario.
2. Con su aprobación: `web.py deploy <slug> --prod --yes`.
3. Primera vez: `web.py domain <slug>` (muestra el plan) → `--yes`: agrega el dominio al proyecto y el CNAME `sub → <project>.pages.dev` (con proxy) en la zona. El certificado tarda unos minutos: `web.py domain <slug>` muestra el estado.
4. Con el dominio activo: `web.py legal <slug> --check --online` (la app enlaza el sitio, la web publica los documentos de la app y la URL de privacidad responde). Decirle al usuario la URL para Play Console (está en `play/app-content.md`) y que la app necesita una versión nueva (`android-release`) para llevar el Acerca de.
5. Commit en el monorepo (push solo si el usuario lo pide).

## Cambios posteriores
Editar → `build` → `qa` → `deploy` (vista previa) → `--prod --yes`. Un documento legal cambia **en la app** (`assets/legal/`) → `web.py legal` → `build` → `deploy`, y la app lo lleva en su próxima versión. Varios sitios: `web.py deploy --changed` publica solo los que cambiaron desde su último deploy de producción (compara con el commit guardado en Pages; un cambio en `packages/` cuenta para todos). `web.py status`: cuentas, tokens, proyectos, último deploy y estado del dominio.

## Reglas
- **Producción y DNS solo con `--yes`** y después de que el usuario vio la vista previa o el plan.
- Tokens: nunca en el chat, el repo ni archivos. `web.py auth` abre una ventana aparte donde se escriben ocultos y los guarda en el Administrador de credenciales.
- Un sitio se publica siempre con la cuenta de su `profile`; el dominio debe ser una zona de esa cuenta.
- Sitios 100 % estáticos (`output: "static"`): sin funciones de servidor, sin almacenamiento pagado. Los archivos grandes (>25 MiB) no van en Pages.
- Nada de afirmaciones sin evidencia en el código; capturas reales.
- Una sola fuente para los textos legales: los Markdown de la app, **solo en inglés, nunca traducidos**. La web los copia (`web.py legal`) y Play enlaza la web.
- Límites del plan gratis de Pages: 100 proyectos por cuenta, 500 deploys al mes por cuenta, 20.000 archivos por sitio, 25 MiB por archivo, 100 dominios por proyecto.

## Errores frecuentes

| Error | Causa |
|---|---|
| "No token for the Cloudflare profile" | Falta `web.py auth --profile <perfil>` en esta PC |
| HTTP 401 | Token inválido, borrado o vencido: crear otro y `auth` de nuevo |
| HTTP 403 | Al token le falta un permiso (Pages Edit, Zone Read, DNS Edit) o no incluye esa cuenta o zona (SETUP.md paso 2) |
| HTTP 403 "Authentication error" al crear el proyecto (pero `status` funciona) | El permiso de Pages quedó en **Read**: **API Tokens → el token → Edit → Cloudflare Pages: Edit**. El token no cambia: no hace falta `auth` de nuevo |
| La vista previa no abre los primeros minutos (error de TLS/SSL) | Cloudflare está emitiendo el certificado de `*.pages.dev` del proyecto nuevo: esperar unos minutos |
| "No zone for <host>" | El dominio no está en esa cuenta de Cloudflare, o el token no tiene Zone Read sobre él |
| "already has other DNS records" | El subdominio ya apunta a otra cosa: decidir con el usuario y cambiarlo a mano |
| `<project>.pages.dev` con un sufijo raro | El nombre ya estaba tomado en Cloudflare: es normal; `domain` usa el subdominio real del proyecto |
| Build: "placeholder text (TODO)" | Quedan textos de la plantilla en `src/i18n`, o un documento legal sin copiar (`web.py legal`) |
| `legal`: "template leftovers" | Un `assets/legal/*.md` de la app todavía tiene `{{…}}`, comentarios `<!--` o `TODO` de la plantilla |
| `legal`: "nothing opens the … document" | Falta el Acerca de con sus documentos (paso 5b) |
| `licenses`: componentes sin licencia | El POM no la declara: buscarla en el repositorio del proyecto (archivo LICENSE) antes de escribir el documento |

## Archivos
- `scripts/web.py`, `SETUP.md`, `references/app-integration.md`, `templates/monorepo/` (lo que crea `init`), `templates/site/` (lo que copia `new`), `templates/android/` (documentos legales, Acerca de en Compose y en Views, recursos), `templates/play/app-content.md`. `config.json` (ruta del monorepo) es por PC y no va al respaldo.
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
