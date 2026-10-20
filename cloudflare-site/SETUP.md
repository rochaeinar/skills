# Configuración

> Los comandos son para **PowerShell** (`$env:USERPROFILE`). En `cmd` se escribe `%USERPROFILE%`. La interfaz de Cloudflare está en inglés: los nombres de botones se dan en inglés.

## Cómo encaja todo

```
Cuenta de Cloudflare (login con su correo)      ->  perfil en el skill (un nombre corto que tú eliges)
   ├─ token de API (uno por cuenta)              ->  Administrador de credenciales: CloudflarePages@<perfil>
   ├─ dominio(s) = "zona" (p. ej. otrodominio.com)
   └─ proyectos de Pages (uno por app; los crea el skill)

Monorepo D:\Projects\websites (uno solo para todas las cuentas)
   ├─ accounts.json            perfil -> Account ID y sus dominios (lo escribe "auth")
   └─ sites\<app>\site.json    "profile": con qué cuenta se publica; "domain": app.otrodominio.com
```

- **Un monorepo para todas las cuentas.** Lo que decide en qué cuenta se publica un sitio es el `profile` de su `site.json`.
- **El subdominio de un sitio debe ser de un dominio de su misma cuenta:** un sitio de la cuenta `cuenta2` no puede usar `timelesslabs.app` si ese dominio está en la cuenta `timeless`.

Según lo que quieras hacer:

| Quiero… | Guía |
|---|---|
| Usar el skill por primera vez en esta PC | **A** |
| Publicar en **otra cuenta de Cloudflare** (otro correo, otros dominios) | **B**, y luego **C** |
| Crear el sitio de una app en una cuenta **ya configurada** | **C** |

---

## Guía A. Primera vez en una PC

| Requisito | Instalar | Comprobar |
|---|---|---|
| Node.js 22.22+ (Astro 7) | nodejs.org (LTS) o `winget install OpenJS.NodeJS.LTS` | `node --version` |
| Python 3.10+ con Pillow | python.org, `python -m pip install --user pillow` | `python -c "import PIL"` |
| git | git-scm.com | `git --version` |
| Microsoft Edge o Google Chrome (capturas de QA y Lighthouse) | viene con Windows | — |
| ffmpeg (solo para importar videos) | `winget install Gyan.FFmpeg` | `ffmpeg -version` |
| adb (solo para capturas del teléfono) | Android Studio → SDK Platform-Tools | `& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices` |

El monorepo. Si ya existe en GitHub, primero `git clone https://github.com/rochaeinar/websites.git D:\Projects\websites`. `init` no sobrescribe nada y recuerda la ruta:

```powershell
python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" init D:\Projects\websites
cd D:\Projects\websites
npm install
```

`wrangler` viene con el monorepo. **No** hace falta `wrangler login`: el skill le pasa el token de cada cuenta solo durante cada deploy.

Luego, por cada cuenta de Cloudflare, sigue la **Guía B**. En otra PC los tokens no se copian: hay que repetir la B para cada cuenta, con un token nuevo o con el mismo si lo tienes.

---

## Guía B. Agregar otra cuenta de Cloudflare

Ejemplo: una cuenta distinta, con el correo `otro@gmail.com` y el dominio `otrodominio.com`. La llamaremos **`cuenta2`**. Usa el nombre que quieras, corto, en minúsculas y sin espacios.

### B1. Entrar a esa cuenta
1. Si tienes otra cuenta abierta en el navegador, cierra la sesión: ícono de perfil (arriba a la derecha) → **Log out**. También puedes usar una ventana privada o un contenedor de Firefox.
2. Entra a **dash.cloudflare.com** con el correo de esa cuenta.
   - Si un mismo correo tiene **varias cuentas**, la lista de cuentas aparece al entrar: elige la que corresponde.

### B2. Tener el dominio en esa cuenta
La zona debe estar **Active**: en **Account home**, el dominio figura con el estado **Active**.
- **Comprarlo en Cloudflare:** **Domain Registration → Register Domains** → buscar → comprar. Queda activo solo.
- **Ya lo tienes en otro registrador** (GoDaddy, Namecheap…): **Account home → Add a domain** → escribir el dominio → plan **Free** → Cloudflare muestra **2 nameservers**. Cámbialos en el panel de tu registrador, en la sección DNS o Nameservers. Puede tardar de minutos a 24 h; Cloudflare envía un correo cuando queda **Active**.

### B3. Copiar el Account ID
Cualquiera de estos sirve; no es secreto:
- En la **barra de direcciones** del navegador: `https://dash.cloudflare.com/<ACCOUNT_ID>/...` (los 32 caracteres después de `.com/`).
- **Workers & Pages** → columna derecha → **Account ID**.
- El dominio → **Overview** → columna derecha → **API** → **Account ID**.

### B4. Crear el token
1. Ícono de perfil (arriba a la derecha) → **Profile** → **API Tokens** → **Create Token**.
2. Al final de la lista: **Custom token** → **Get started**.
3. **Token name:** `websites-cuenta2`.
4. **Permissions**: tres filas; cada fila nueva se agrega con **+ Add more**. En cada fila se eligen sus tres listas:
   - **Account** → **Cloudflare Pages** → **Edit**
   - **Zone** → **Zone** → **Read**
   - **Zone** → **DNS** → **Edit**
5. **Account Resources:** **Include** → la cuenta de este correo.
6. **Zone Resources:** **Include** → **All zones from an account** → esa cuenta. Así sirve también para los dominios que agregues después. Si prefieres limitarlo: **Specific zone** → `otrodominio.com`.
7. **Client IP Address Filtering** y **TTL**: déjalos vacíos, sin vencimiento.
8. **Continue to summary** → **Create Token**.
9. **Deja esa pantalla abierta.** El token se muestra **una sola vez**. No lo pegues en el chat ni en archivos.

### B5. Guardarlo en el skill
En PowerShell:

```powershell
python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" --repo D:\Projects\websites auth --profile cuenta2
```

Se abre **otra ventana**:
1. **Account ID:** pega el de B3 y presiona Enter.
2. **API token:** pégalo con **clic derecho**. No se ve mientras se escribe. Presiona Enter.
3. Debe decir `OK: saved as CloudflarePages@cuenta2` y listar las zonas que ve el token, por ejemplo `otrodominio.com`. Presiona Enter para cerrar.

El token queda en el **Administrador de credenciales de Windows**, cifrado y legible solo por tu usuario de Windows. La cuenta y sus dominios se anotan en `accounts.json`, sin secretos.

### B6. Comprobar

```powershell
python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" --repo D:\Projects\websites status
```

Debe aparecer `account cuenta2 <Account ID> token OK zones: otrodominio.com`. Si no aparece el dominio, revisa B2 (zona **Active**) y B4 paso 6.

Listo: la cuenta está configurada. Para crear sitios en ella, sigue la **Guía C** con `--profile cuenta2`.

---

## Guía C. Crear el sitio de una app (en una cuenta ya configurada)

Ejemplo: la app "Mi App" (`com.ejemplo.miapp`) en `miapp.otrodominio.com`, cuenta `cuenta2`.

1. **Pídeselo a Claude:** "crea la web de Mi App en miapp.otrodominio.com con la cuenta cuenta2". Ten a mano la carpeta del proyecto de la app y la de sus imágenes. Claude ejecuta:
   ```powershell
   python "$env:USERPROFILE\.claude\skills\cloudflare-site\scripts\web.py" --repo D:\Projects\websites new miapp --profile cuenta2 --domain miapp.otrodominio.com --package com.ejemplo.miapp --name "Mi App" --app-project D:\Projects\Android\mi-app --assets D:\Documents\MiApp\Images
   ```
   Esto crea `sites\miapp\` con su `site.json` (`"profile": "cuenta2"`).
2. **Análisis, recursos, capturas y mockups:** Claude los hace y te muestra los mockups en Claude Design para que apruebes uno (ver SKILL.md).
3. **Implementar y revisar:** `build` y `qa`.
4. **Vista previa:** `deploy miapp`.
   - La primera vez **crea el proyecto de Pages** en la cuenta `cuenta2`; no se crea a mano en el dashboard.
   - Te da una URL `https://preview.miapp.pages.dev` para revisar.
5. **Producción:** cuando apruebes, `deploy miapp --prod --yes`. Queda en `https://miapp.pages.dev`.
6. **Dominio propio, solo la primera vez:** `domain miapp` muestra qué va a hacer, y `domain miapp --yes` lo aplica:
   - agrega `miapp.otrodominio.com` al proyecto de Pages;
   - crea el CNAME `miapp → miapp.pages.dev` (con proxy) en la zona.

   El certificado HTTPS tarda unos minutos. Con `domain miapp` se ve el estado (`active` cuando ya está).
7. Commit y push del monorepo.

Para cambios posteriores, se repiten los pasos 3 a 5. El dominio ya queda conectado.

---

## Referencia

### Renovar, revocar o mover un token
- **Renovar o cambiar:** crea otro token (B4), corre `auth --profile <perfil>` otra vez (reemplaza el guardado) y borra el viejo en **API Tokens**.
- **Si se filtró:** **API Tokens** → **⋯** junto al token → **Roll** o **Delete**, y luego `auth` de nuevo.
- **Fuera de Windows:** variables `CLOUDFLARE_API_TOKEN_<PERFIL>` y `CLOUDFLARE_ACCOUNT_ID_<PERFIL>`.

### Mover un sitio a otra cuenta
1. Cambia `profile` y `domain` en su `site.json`. El dominio debe ser de la nueva cuenta.
2. `deploy --prod --yes` en la nueva cuenta y luego `domain --yes`.
3. Borra el proyecto viejo a mano: cuenta vieja → **Workers & Pages** → el proyecto → **Settings** → **Delete project**.

### Analítica (opcional, gratis y sin cookies)
En la cuenta del sitio: **Analytics & Logs → Web Analytics → Add a site** → el hostname. Copia el `token` del fragmento que muestra (es público) a `analytics_token` del `site.json` y vuelve a publicar.

### Límites del plan gratis de Pages (por cuenta)
- 100 proyectos (no se suele ampliar).
- 500 deploys al mes.
- 20.000 archivos por sitio, 25 MiB por archivo.
- 100 dominios propios por proyecto.

No hay costo por tráfico ni por guardar archivos estáticos. Con más de 100 sitios en una cuenta, se reparten en otra cuenta (Guía B).

### Errores al configurar

| Mensaje | Qué hacer |
|---|---|
| La ventana de `auth` dice "does not look like an Account ID" | El Account ID tiene 32 caracteres (0-9, a-f): cópialo de la URL (B3) |
| HTTP 401 en `auth` o al publicar | Token mal copiado, borrado o vencido: crea otro (B4) y `auth` de nuevo |
| HTTP 403 | Al token le falta un permiso o no incluye esa cuenta o zona: **API Tokens** → el token → **Edit** (B4 pasos 4 a 6) |
| `status` no muestra el dominio | La zona no está **Active** en esa cuenta (B2), o el token no la incluye (B4 paso 6) |
| `domain`: "No zone for …" | El subdominio es de un dominio de otra cuenta: usa un dominio de la cuenta del `profile` |

## Ejemplo real

- Monorepo `D:\Projects\websites` (GitHub `rochaeinar/websites`).
- Perfil `timeless`: cuenta `335e9d8554b7425859425f66d2c320c8`, dominio `timelesslabs.app`.
- Sitio `bibleversions` → `bibleversions.timelesslabs.app` (la app lo enlaza desde *About*). Proyecto de la app: `D:\Projects\Android\bible-versions`; imágenes: `D:\Documents\BibleVersions\Images`.
