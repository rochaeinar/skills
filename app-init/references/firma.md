# Firma: el certificado de subida, paso a paso

Se lo guía al usuario **la primera vez**, un paso a la vez, esperando su "listo" entre pasos. Claude nunca ve ni escribe la contraseña.

## Qué es cada clave (explicarlo en una línea al usuario)

- **Clave de firma de la app**: la que firma lo que instalan los usuarios. Con **Play App Signing** (obligatorio para apps nuevas desde 2021) la genera y la guarda Google; no se descarga.
- **Clave de subida** (la que creamos aquí): firma el AAB que subimos. Si se pierde o se filtra, Google la **restablece** (Play Console → Integridad de la app → Solicitar restablecimiento de la clave de subida) con un certificado nuevo. Igual hay que cuidarla: con ella alguien podría subir versiones si además entra a la cuenta.
- Formato PKCS12, RSA 4096, válida 10.000 días (Play exige validez hasta después del 22-10-2033), alias `upload`. Una sola contraseña para el almacén y la clave (PKCS12 no admite dos).

## Paso 1. Bitwarden: crear el ítem y generar la contraseña (antes de crear la clave)

1. Bitwarden → **Nuevo → Inicio de sesión** (*Login*).
2. **Nombre**: `Android · <App> · upload key`. Carpeta: `Android / Keystores` (crearla la primera vez).
3. **Usuario**: `upload` (el alias).
4. **Contraseña**: botón **Generar** → 24 caracteres o más, mayúsculas, minúsculas, números y símbolos. Evitar `"`, `'`, `` ` `` y `$` si el generador lo permite (la contraseña pasa por PowerShell y Gradle). **Guardar el ítem ya**, así la contraseña nunca se pierde.
5. Dejar Bitwarden abierto: la contraseña se copia de ahí en el paso 2.

## Paso 2. Crear la clave (ventana aparte)

`appinit.py keystore <repo>` abre PowerShell con `setup-signing.ps1 -Create`. El usuario:
1. Pega la contraseña de Bitwarden dos veces (no se ve al escribir).
2. Confirma la organización (la marca) y el país (2 letras).

El script crea `D:\Documents\Apps\<App>\KeyStore\upload.jks`, comprueba la contraseña contra la clave, la guarda en el **Administrador de credenciales de Windows** (`<slug>-release-signing`, usuario = alias) y escribe junto a la clave lo público: `keystore-info.json` (SHA-256, SHA-1, vencimiento) y `upload_certificate.pem`. Nunca sobrescribe una clave que ya existe.

## Paso 3. Probar la firma

Claude corre `gradlew bundleRelease` (sin `UNSIGNED` en la salida) y `jarsigner -verify app/build/outputs/bundle/release/app-release.aab` (`jar verified`). Con `signing.signDebug=true`, el debug también sale firmado con la clave de subida (`apksigner verify --print-certs` muestra el mismo SHA-256).

## Paso 4. Respaldo (no se cierra el skill sin esto)

1. **Bitwarden, en el mismo ítem**:
   - **Adjunto**: `upload.jks` (*Attachments* necesita Bitwarden Premium u organización).
     Sin Premium: una **Nota segura** aparte, `Android · <App> · upload.jks (base64)`, con el contenido de `[Convert]::ToBase64String([IO.File]::ReadAllBytes("<ruta>\upload.jks"))`. Lo copia el usuario en su PowerShell (`| Set-Clipboard`), no Claude. Para restaurar: `[IO.File]::WriteAllBytes("<ruta>\upload.jks", [Convert]::FromBase64String((Get-Clipboard -Raw)))`.
   - **Campos personalizados** (texto): `package`, `SHA-256`, `SHA-1`, `válida hasta` (de `keystore-info.json`), `ruta` (`D:\Documents\Apps\<App>\KeyStore\upload.jks`) y `credencial Windows` (`<slug>-release-signing`).
   - **Notas**: "Clave de SUBIDA. Play App Signing guarda la de firma. Si se pierde: Integridad de la app → restablecer clave de subida."
2. **Copia sin conexión**: una USB o un disco externo con un contenedor cifrado (BitLocker To Go o VeraCrypt) que guarde la carpeta `KeyStore\` de todas las apps. Actualizarlo cada vez que se crea una clave.
3. Bitwarden con **verificación en dos pasos** y su **código de recuperación** impreso o guardado fuera de Bitwarden.
4. Cuando el usuario confirme, Claude anota en `app.json`: `"signing": {"backup": {"bitwarden": "<fecha>", "offline": "<fecha o pendiente>"}}`.

## Paso 5. Play Console (cuando se cree la app ahí; lo hace `play-console`)

- Al subir el primer AAB, aceptar **Play App Signing** (lo propone por defecto). Google registra nuestra clave como **de subida**.
- Comprobar: **Prueba y lanzamiento → Integridad de la app → Firma de apps → Certificado de clave de subida**: el SHA-256 debe ser el de `keystore-info.json`.
- Si la app usa **Google Sign-In / Drive** (synchronizer) o Firebase: el cliente OAuth y Firebase necesitan **el SHA-1 de las dos claves**: la de subida (builds de debug y de prueba firmadas aquí) y la de firma de la app (copiarla de esa misma pantalla de Play).

## Otra PC, o una clave que ya existe

1. Restaurar `upload.jks` desde Bitwarden a `D:\Documents\Apps\<App>\KeyStore\`.
2. `appinit.py keystore <repo> --register`: pide alias y contraseña, los comprueba contra la clave y los guarda.

## Proyecto con firma vieja (keystore.properties, contraseñas en el build, otra carpeta)

`references/repo-existente.md`, paso 4. Nunca se crea una clave nueva para una app **ya publicada** sin preguntar: la app publicada se sigue firmando con su clave de subida actual. Si esa clave es la única (app anterior a Play App Signing) o se desconoce cuál es, mirar en Play Console → Integridad de la app qué certificado espera Google y comparar su SHA-256 con el de la clave local (`keytool -list -v`).

## Clave comprometida (contraseña en git, en un chat o en un archivo)

1. Crear una clave de subida nueva (`-Create` con otro nombre de archivo, p. ej. `upload-2026.jks`, y `signing.keystore` en `gradle.properties`).
2. Play Console → Integridad de la app → **Solicitar restablecimiento de la clave de subida** con su `upload_certificate.pem`. Google tarda unos días.
3. Borrar la contraseña vieja de donde estuvo (historial de git: con el usuario, `git filter-repo`), y el ítem viejo de Bitwarden marcado como "revocada".
