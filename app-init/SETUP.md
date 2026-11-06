# app-init: configuración (una vez por PC)

Comandos para **PowerShell**. Nombres de la interfaz en español / inglés.

## 1. Herramientas

- **Python 3** (`python --version`) y **git**.
- **Android Studio** con su JBR: trae `keytool` y `jarsigner` (`C:\Program Files\Android\Android Studio\jbr\bin\`). El Android SDK en `%LOCALAPPDATA%\Android\Sdk`.
- **Módulo CredentialManager** de PowerShell (lo usan `setup-signing.ps1` y Gradle para leer la contraseña). `setup-signing.ps1` lo instala solo la primera vez; a mano:
  ```powershell
  Install-Module CredentialManager -Scope CurrentUser -Force
  ```
- Las rutas por defecto (`D:\Documents\Apps`, `D:\Projects\Android`) se cambian con las variables `APP_INIT_APPS_ROOT` y `APP_INIT_PROJECTS_ROOT`.

## 2. Bitwarden (respaldo de claves y contraseñas)

1. Cuenta en [bitwarden.com](https://bitwarden.com) con contraseña maestra fuerte.
2. **Ajustes → Seguridad → Inicio de sesión en dos pasos / Two-step login**: activar (app de autenticación o llave). Guardar el **código de recuperación** fuera de Bitwarden (impreso).
3. Crear la carpeta `Android / Keystores`.
4. **Premium** (unos USD 10 al año) permite **adjuntar** el `.jks` al ítem. Sin Premium, se guarda en base64 en una nota segura (`references/firma.md`, paso 4).
5. Extensión del navegador o app de escritorio: para copiar la contraseña generada al crear la clave.

## 3. Bitbucket (crear repos automáticamente)

Bitbucket Cloud reemplazó las *app passwords* por **API tokens con permisos** (las *app passwords* dejaron de crearse el 9-9-2025 y de funcionar el 9-6-2026).

1. [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) → **Crear token de API con permisos / Create API token with scopes**.
2. Nombre `app-init <PC>`, vencimiento (máx. 1 año: anotarlo), aplicación **Bitbucket**.
3. Permisos:
   - `read:user:bitbucket`, `read:workspace:bitbucket`: comprobar el token y listar los workspaces.
   - `read:project:bitbucket`: poner el repo en un proyecto.
   - `read:repository:bitbucket`, `write:repository:bitbucket`: leer y hacer push.
   - `admin:repository:bitbucket`: **crear** repos. Si la API responde 403 al crear dentro de un proyecto, agregar `admin:project:bitbucket`.
4. Copiar el token (se muestra una sola vez) y guardarlo:
   ```powershell
   python "$env:USERPROFILE\.claude\skills\app-init\scripts\appinit.py" bitbucket auth
   ```
   Se abre una ventana aparte: correo de la cuenta de Atlassian y el token (oculto). Queda en el Administrador de credenciales como `Bitbucket-API` (usuario = correo). Guardarlo también en Bitwarden (`Bitbucket · API token · <PC>`, con la fecha de vencimiento).
5. Comprobar: `appinit.py bitbucket check` → `OK: <usuario>` y la lista de workspaces.
6. **git push con el token**: la primera vez que git pida credenciales para `bitbucket.org`, usuario = tu usuario de Bitbucket (o `x-bitbucket-api-token-auth`) y contraseña = el token. Git Credential Manager lo recuerda.

Al vencer el token: crear otro y repetir el paso 4.

## 4. Perfiles de los otros skills

app-init solo **elige** perfiles. Si falta alguno, se configura con el skill que lo usa:
- Play Console: `play-console/SETUP.md` (cuenta de servicio por cuenta de desarrollador → `PlayConsole@<perfil>`).
- Cloudflare: `cloudflare-site/SETUP.md` (`CloudflarePages@<perfil>` y `accounts.json`).
- YouTube: `app-promo-video/SETUP.md` 6.4 (`PromoVideo-YouTube@<perfil>`).

`appinit.py profiles` muestra los que hay en esta PC.
