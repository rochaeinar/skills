# Configuración desde cero (otra PC u otra cuenta)

Todo lo que hay que tener antes de usar el skill. Hacerlo una vez por PC y por cuenta. Las claves nunca van en archivos ni en el chat: viven en el **Administrador de credenciales de Windows** (o en variables de entorno en otros sistemas).

Orden recomendado: 1 → 2 → 3 (lo mínimo para un video sin IA ni voz), luego 4 y 5 (voz, música y gancho con IA), y 6 solo para subir a YouTube por API.

---

## 1. Herramientas de la PC

| Herramienta | Para qué | Instalar | Comprobar |
|---|---|---|---|
| Python 3.10+ con Pillow | Todos los scripts | python.org; `pip install pillow` | `python -c "import PIL"` |
| Node.js 20+ | Remotion (render) | nodejs.org | `node --version` |
| ffmpeg y ffprobe | Recortar, medir, normalizar volumen | Windows: `winget install Gyan.FFmpeg` | `ffmpeg -version` (en una terminal nueva) |
| Android SDK platform-tools (adb) | Grabar el teléfono | Android Studio | `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe devices` |
| JDK | Maestro | El de Android Studio (`C:\Program Files\Android\Android Studio\jbr`) | — |
| Maestro CLI | Manejar la app mientras graba | github.com/mobile-dev-inc/maestro/releases → `maestro.zip` → `%USERPROFILE%\.maestro\bin` | `%USERPROFILE%\.maestro\bin\maestro.bat --version` |
| Módulo PowerShell CredentialManager | Guardar claves | `Install-Module CredentialManager -Scope CurrentUser` | `Get-Module -ListAvailable CredentialManager` |

Las dependencias de Remotion se instalan solas la primera vez que se renderiza (`npm install` en `remotion/`, ~260 paquetes).

## 2. El teléfono

- **Depuración USB** activada (Ajustes → Acerca del teléfono → tocar 7 veces "Número de compilación" → Opciones de desarrollador → Depuración USB).
- Conectado por USB, **desbloqueado**, con la app instalada y con datos realistas (marcadores, historial, planes).
- El **idioma del teléfono** debe ser el del video que se graba (la app lo sigue).
- Si la app es la de Play Store y hace falta la versión debug: no se puede instalar encima (otra firma). El usuario sincroniza sus datos y desinstala él; antes, respaldar el APK de Play (`adb shell pm path <app>` + `adb pull`).

## 3. Guardar una clave (se usa en los pasos 4, 5 y 6)

En una ventana de PowerShell **aparte** (nunca en el chat), una sola línea; pide el target y la clave sin mostrarla ni guardarla en el historial:

```powershell
Import-Module CredentialManager; $t = Read-Host 'Target'; $s = Read-Host 'Clave' -AsSecureString; $k = [System.Net.NetworkCredential]::new('', $s).Password; New-StoredCredential -Target $t -UserName api -Password $k -Persist LocalMachine | Out-Null; Remove-Variable k, s; "Guardada ${t}: " + [bool](Get-StoredCredential -Target $t)
```

Si una clave se pegó por error en un comando, limpiar el historial:

```powershell
$h = (Get-PSReadLineOption).HistorySavePath; (Get-Content $h) | Where-Object { $_ -notmatch 'sk_[A-Za-z0-9]{20,}' -and $_ -notmatch '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{20,}' } | Set-Content $h -Encoding utf8; Clear-History; [Microsoft.PowerShell.PSConsoleReadLine]::ClearHistory()
```

y cerrar esa ventana. Si la clave salió de la PC (chat, documento), revocarla y crear otra.

En macOS o Linux: variables de entorno `ELEVENLABS_API_KEY`, `FAL_KEY`.

## 4. ElevenLabs: voz, música y efectos

1. Cuenta en **elevenlabs.io**.
2. Plan **Starter** (≈ $6/mes, 40.000 créditos). Es el mínimo con **uso comercial sin atribución**; el plan gratuito no sirve para anuncios. Un video completo usa ~400-1.000 créditos.
   - Hay **pago por uso** sin suscripción (saldo válido 12 meses), pero en octubre de 2026 la licencia comercial de ese modo no estaba clara: confirmarla con soporte antes de usarlo.
3. **Developers → API Keys → Create API Key**, nombre `promo-video`:
   - Acceso: **Texto a voz**, **Generación de música**, **Efectos de sonido**; **Voces: Leído**; **Modelos** y **Usuario: Acceso**. Todo lo demás: sin acceso.
   - **Límite de créditos** por período (p. ej. 25.000) y **desactivación automática si se filtra**: activada. Sin restricción por IP.
4. Guardar con el paso 3 como **`PromoVideo-ElevenLabs`**.
5. Comprobar (sin mostrar la clave):
   ```powershell
   Import-Module CredentialManager; $k=(Get-StoredCredential -Target PromoVideo-ElevenLabs).GetNetworkCredential().Password; (Invoke-RestMethod -Uri https://api.elevenlabs.io/v1/user/subscription -Headers @{'xi-api-key'=$k}).tier; Remove-Variable k
   ```
   Debe decir `starter` (o el plan contratado).

Licencia de la música: elevenlabs.io/music-terms (verificada el 2026-10-18: desde Starter, uso comercial online sin atribución, salvo cine, TV, radio y videojuegos de estudio; los planes Free a Pro son "para uso individual").

## 5. fal.ai: escenas de IA del gancho

1. Cuenta en **fal.ai**.
2. **Billing → recargar saldo** (prepago, sin suscripción). Unos $13 alcanzan para un video con 3 ganchos; un idioma más cuesta $0 (las escenas se reutilizan).
3. **Keys → Add key**, nombre `promo-video`, alcance **API**.
4. Guardar con el paso 3 como **`PromoVideo-Fal`**.

Precios de referencia (sin audio, que es como se usan): Veo 3.1 final ≈ $0,80 por escena de 4 s; Veo 3.1 Lite borrador ≈ $0,12; imagen temporal ≈ $0,025.

## 6. YouTube (solo para subir por API)

Sin esto el skill igual prepara todo para subir a mano (`publish.py prepare`).

### 6.1 El canal (una vez por cuenta)

1. Entrar a **youtube.com** con la cuenta de Google que será dueña del canal.
2. Crear el canal. El menú de la foto no siempre muestra la opción (y cambia con el idioma de la interfaz); lo más seguro es el enlace directo **youtube.com/create_channel**. Alternativas: foto → **Configuración / Settings** → **Crear un canal / Create a channel** (o **Agregar o administrar tus canales / Add or manage your channel(s)**), o entrar a **studio.youtube.com**, que lo pide si no hay canal.
   - **Nombre / Name:** el de la app. **Identificador / Handle:** p. ej. `@<app>app`. **Foto / Picture:** el ícono de la app.
   - Si el menú ya muestra **Tu canal / Your channel**, la cuenta ya tiene uno (con el nombre del perfil): cambiarle el nombre en YouTube Studio → **Personalización / Customization → Información básica / Basic info**.
3. **Verificar el canal por teléfono** en **youtube.com/verify** (SMS; en inglés, "Verify"). Sin esto no hay miniaturas personalizadas; puede tardar hasta 24 h.

### 6.2 Proyecto de Google Cloud (una vez por cuenta)

Con la **misma cuenta** del canal:

(Nombres de la interfaz en español / inglés.)

1. **console.cloud.google.com** → aceptar términos → selector de proyecto → **Proyecto nuevo / New project** (p. ej. "<App> Promo") y dejarlo seleccionado.
2. ☰ → **APIs y servicios / APIs & Services → Biblioteca / Library** → **YouTube Data API v3** → **Habilitar / Enable**.
3. ☰ → **APIs y servicios → Pantalla de consentimiento de OAuth / OAuth consent screen** (o **Google Auth Platform**): nombre de la app, correo de asistencia (**User support email**), público **Externo / External**, contacto; en **Público / Audience → Usuarios de prueba / Test users** agregar la cuenta del canal.
4. ☰ → **Credenciales / Credentials** (o **Clientes / Clients**) → **Crear credenciales / Create credentials → ID de cliente de OAuth / OAuth client ID** → **App de escritorio / Desktop app** → **Descargar JSON / Download JSON**. Guardarlo fuera de cualquier repo.

### 6.3 Autorizar (una vez por PC)

```
python -I "%USERPROFILE%\.claude\skills\app-promo-video\scripts\publish.py" auth "<ruta>\client_secret.json"
```

Se abre el navegador: elegir la cuenta del canal → aviso **"Google no verificó esta app" / "Google hasn't verified this app"** (normal, la app es propia) → **Avanzado / Advanced → Ir a ... (no seguro) / Go to ... (unsafe)** → aceptar los permisos (**Continuar / Continue**). Debe terminar con `OK: authorized for the channel '<canal>'`. Guarda `PromoVideo-YouTube-Client` (id y secreto del cliente) y `PromoVideo-YouTube` (token de actualización).

- **Contenedores de Firefox u otro perfil:** con `--no-browser` el script solo imprime el enlace; pegarlo en la pestaña donde está iniciada la cuenta del canal (la respuesta vuelve a `127.0.0.1`, sirve cualquier navegador de la PC). El enlace sirve una sola vez y el script espera 15 minutos.
- **Error 403: access_denied** ("...can only be accessed by developer-approved testers"): la cuenta elegida no está en **Usuarios de prueba / Test users** (paso 6.2.3). Agregarla, esperar 1-2 minutos y volver a abrir el enlace.
- Con la app en modo **Prueba / Testing**, la autorización **caduca a los 7 días** (los videos subidos no se ven afectados; solo hay que repetir 6.3). **Para que no caduque:**
  1. Google Cloud Console → **Google Auth Platform → Público / Audience** → **Estado de publicación / Publishing status: Testing** → **Publicar app / Publish app** → confirmar.
  2. Repetir 6.3 una vez para obtener un token que ya no caduca.
  3. El aviso de "app no verificada" sigue apareciendo al autorizar (se acepta: la app es propia). Las apps sin verificar tienen un límite de usuarios, que no importa para un uso personal.

### 6.4 Varias cuentas de Google (un perfil por cuenta)

La generación (ElevenLabs, fal.ai) es compartida por todas las apps. Lo que cambia por cuenta es **YouTube**: cada cuenta de Google tiene **su propio proyecto de Google Cloud** y su propio canal, y en el skill un **perfil** (un nombre corto, p. ej. `otrodev`).

1. Con la **otra cuenta de Google**, repetir 6.1 (canal) y 6.2 (proyecto, API, pantalla de consentimiento con esa cuenta en **Test users**, cliente de escritorio) y descargar **su** JSON.
2. Autorizar con el nombre del perfil:
   ```
   python -I "%USERPROFILE%\.claude\skills\app-promo-video\scripts\publish.py" auth "<ruta>\client_secret.json" --no-browser --profile otrodev
   ```
   Abrir el enlace en el navegador (o contenedor) donde está iniciada **esa** cuenta. Guarda `PromoVideo-YouTube-Client@otrodev` y `PromoVideo-YouTube@otrodev`.
3. En el `video.json` de cada app que sube a ese canal: `"youtube_profile": "otrodev"`. Sin esa línea se usa la cuenta sin perfil (la primera que se configuró).
4. `publish.py upload` muestra al empezar el perfil y el canal que va a usar, y guarda el canal en `publish.<locale>.uploaded`. Para una subida puntual a otro canal: `--profile <nombre>`.

Cada perfil tiene su propio vencimiento de 7 días (modo Prueba) y su propia auditoría, porque cada uno es un proyecto distinto.

### 6.5 Auditoría de la API (para que no quede en privado)

Los proyectos creados después del 28-07-2020 y **sin auditoría** tienen sus subidas por API **forzadas a privado** (documentación de `videos.insert`). En la práctica (prueba del 2026-10-19 con un proyecto nuevo sin auditoría) YouTube dejó los dos videos en **oculto**, como se pidió: comprobarlo en Studio después del procesamiento. `publish.py upload` lee la privacidad real y avisa. Para quitar el bloqueo: formulario **"YouTube API Services – Audit and Quota Extension"** (gratis, tarda días o semanas). Mientras tanto: cambiar la visibilidad en YouTube Studio si lo permite, o subir a mano con `upload/<nombre>/CHECKLIST.md`.

**No automatizar YouTube Studio** con Playwright, Selenium ni extensiones: va contra los términos de YouTube y arriesga el canal.

### 6.6 Google Play (para pegar el enlace)

En Play Console → **Presencia en Play Store → Ficha principal → <idioma> → Video de YouTube**: el enlace `https://youtu.be/<id>` sin parámetros. El video debe ser **oculto o público** (no privado), **sin monetización** y con la **inserción permitida**.

---

## Comprobación final

| Qué | Comando o señal |
|---|---|
| Herramientas | `ffmpeg -version`, `node --version`, `adb devices` (el teléfono como `device`) |
| ElevenLabs | el comando del paso 4.5 devuelve el plan |
| fal.ai | `broll.py ... --stage placeholder` genera una imagen (≈ $0,025) |
| YouTube | `publish.py auth` termina con `OK: authorized for the channel` |
| Todo | `capture.py`, `process_clips.py`, `audio.py`, `render.py --still 2` sin errores |
