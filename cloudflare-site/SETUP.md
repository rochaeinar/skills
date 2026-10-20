# Configuración desde cero

> Los comandos son para **PowerShell** (`$env:USERPROFILE`). En `cmd` se escribe `%USERPROFILE%`.

Paso 1 una vez por PC; pasos 2 y 3 una vez por **cuenta de Cloudflare** (perfil); paso 4 por **dominio**. Nombres de la interfaz de Cloudflare en inglés (la interfaz está en inglés).

## 1. La PC

| Requisito | Instalar | Comprobar |
|---|---|---|
| Node.js 22.22+ (Astro 7) | nodejs.org (LTS) o `winget install OpenJS.NodeJS.LTS` | `node --version` |
| Python 3.10+ con Pillow | python.org, `python -m pip install --user pillow` | `python -c "import PIL"` |
| git | git-scm.com | `git --version` |
| Microsoft Edge o Google Chrome (capturas de QA y Lighthouse) | viene con Windows | — |
| ffmpeg (solo para importar videos) | `winget install Gyan.FFmpeg` | `ffmpeg -version` |
| adb (solo para capturas del teléfono) | Android Studio → SDK Platform-Tools | `$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe devices` |

El monorepo (una vez por PC; si ya existe en git, clonarlo y correr igual `init`, que no sobrescribe nada y recuerda la ruta):

```
python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" init D:\Projects\websites
cd D:\Projects\websites
npm install
```

`wrangler` se instala con el monorepo (`npm install`); no hace falta `wrangler login`: el skill le pasa el token de cada cuenta solo durante cada deploy.

## 2. Token de API de una cuenta de Cloudflare

Con la cuenta de Cloudflare que tiene (o tendrá) los dominios de esas apps:

1. **dash.cloudflare.com** → ícono de perfil (arriba a la derecha) → **Profile** → **API Tokens** → **Create Token**.
2. Al final de la lista: **Custom token → Get started**.
3. **Token name:** `websites-<perfil>` (p. ej. `websites-timeless`).
4. **Permissions**: tres filas (cada fila nueva con **+ Add more**), eligiendo en sus tres listas:
   - **Account** → **Cloudflare Pages** → **Edit**
   - **Zone** → **Zone** → **Read**
   - **Zone** → **DNS** → **Edit**
5. **Account Resources:** Include → *esa cuenta*.
6. **Zone Resources:** Include → **Specific zone** → el dominio (agregar una fila por dominio) o **All zones from an account** → esa cuenta (más cómodo con muchos dominios).
7. **Client IP Address Filtering** y **TTL**: vacíos (sin vencimiento). Si se pone vencimiento, anotarlo: al vencer da HTTP 401.
8. **Continue to summary → Create Token**. Cloudflare lo muestra **una sola vez**: dejarlo en pantalla para el paso 3, no pegarlo en el chat ni en archivos.
9. **Account ID:** en el inicio de la cuenta (**Account home**) → menú **⋯** junto al nombre de la cuenta → **Copy account ID**; o en **Overview** de cualquier dominio, columna derecha → **API → Account ID**. No es secreto.

Un token por cuenta. Con 3 cuentas: 3 tokens y 3 perfiles (`timeless`, `cuenta2`, `cuenta3`).

## 3. Guardarlo en el skill

```
python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" --repo D:\Projects\websites auth --profile <perfil>
```

Se abre **otra ventana**: pide el Account ID y el token (oculto; pegar con clic derecho). Lo comprueba contra Cloudflare (permiso de Pages, zonas que ve), lo guarda en el **Administrador de credenciales de Windows** como `CloudflarePages@<perfil>` (usuario = Account ID, contraseña = token; cifrado por Windows, solo legible por tu usuario) y anota la cuenta y sus zonas en `accounts.json` del monorepo (sin secretos). Comprobar: `web.py status` → `token OK`.

- Cambiar o renovar el token: crear otro en Cloudflare, `auth` otra vez (lo reemplaza) y borrar el viejo en **API Tokens**.
- Si se filtra: **API Tokens → ⋯ → Roll** (o Delete) en Cloudflare y `auth` de nuevo.
- Otra PC: el token no se copia; crear uno nuevo o volver a ingresarlo con `auth`.
- Fuera de Windows: variables `CLOUDFLARE_API_TOKEN_<PERFIL>` y `CLOUDFLARE_ACCOUNT_ID_<PERFIL>`.

## 4. Cada dominio

1. El dominio debe estar **en la misma cuenta** que los sitios que lo usan: comprado en Cloudflare Registrar, o agregado con **Add a domain** y los *nameservers* de Cloudflare en el registrador (estado **Active**).
2. Si el token es por zonas específicas, agregarle la zona nueva (**API Tokens → Edit**).
3. Nada más: `web.py domain <slug> --yes` crea el subdominio (CNAME con proxy a `<project>.pages.dev`) y lo conecta a Pages; Cloudflare emite el certificado HTTPS en minutos. Cada app es un subdominio (`app.dominio.com`); el CDN y el caché de Cloudflare se aplican solos.

## Proyectos de Pages: no se crean a mano

No hace falta entrar a **Workers & Pages → Create** en el dashboard. El primer `web.py deploy <slug>` crea el proyecto de Pages por la API (nombre = `project` del `site.json`, rama de producción `main`) y sube el sitio compilado (*Direct Upload*: sin conectar GitHub; el build se hace en la PC). Después aparece en **Workers & Pages** con sus deploys, la URL `<project>.pages.dev` y la de vista previa `preview.<project>.pages.dev`. El dominio propio lo agrega `web.py domain`.

## 5. Analítica (opcional, gratis y sin cookies)

**Analytics & Logs → Web Analytics → Add a site** → hostname del sitio → copiar el `token` del fragmento que muestra (es público) a `analytics_token` del `site.json`, y volver a publicar.

## Límites del plan gratis de Pages

100 proyectos por cuenta (no se suele ampliar), 500 deploys al mes por cuenta, 20.000 archivos por sitio, 25 MiB por archivo, 100 dominios propios por proyecto. Sin costo por tráfico ni almacenamiento de archivos estáticos. Con más de 100 sitios en una cuenta habría que repartirlos en otra cuenta o pasar a Workers Static Assets.

## Ejemplo real

Monorepo `D:\Projects\websites` (GitHub `rochaeinar/websites`); perfil `timeless` (dominio `timelesslabs.app`); sitio `bibleversions` → `bibleversions.timelesslabs.app` (la app lo enlaza desde *About*), proyecto de la app `D:\Projects\Android\bible-versions`, imágenes `D:\Documents\BibleVersions\Images`.
