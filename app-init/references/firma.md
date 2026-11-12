# Firma: el certificado de subida, paso a paso

Se lo guía al usuario **la primera vez**, un paso a la vez, esperando su "listo" entre pasos. Claude nunca ve ni escribe la contraseña.

## El modelo: una sola clave para todo (explicarlo en una línea al usuario)

- **Una clave por app** (`upload.jks`, alias de `app.json`; Erasoft: `Era Soft Labs`) firma el **debug**, el **release** y, en Google Play, es a la vez la **clave de subida** y la **clave de firma de la app**. Es el modelo de Bible Versions, Tracker y Forever Note.
- En Play se activa con **Play App Signing con clave propia**: en el primer lanzamiento se sube la clave cifrada con **PEPK** (paso 5). Google guarda una copia y firma con ella lo que instalan los usuarios: el mismo certificado que los builds locales.
- Ventajas: un solo SHA-1 (Google Sign-In, Drive, Firebase), los builds locales sin `applicationIdSuffix` se instalan encima del de Play sin borrar datos, una sola cosa que respaldar.
- Cuidado: es la **identidad permanente** de la app. Si se **pierde**, Google tiene la copia y se pide un restablecimiento de la clave de subida. Si se **filtra** (archivo + contraseña), alguien puede firmar APKs que se instalan encima de la app fuera de Play, y Google solo permite actualizar la clave de firma una vez. Por eso el archivo y la contraseña nunca van juntos sin cifrar.
- El archivo PKCS12 ya está cifrado con la contraseña: puede estar en la carpeta de la app, en Mega y en Bitwarden. La contraseña, solo en Bitwarden y en el Administrador de credenciales.
- Formato PKCS12, RSA 4096. Una sola contraseña para el almacén y la clave (PKCS12 no admite dos).
- **Datos del certificado** (públicos: van en cada APK y no se cambian después): los de la marca en `BRANDS` de `appinit.py`, copiados a `app.json` (`signing.dname`, `signing.alias`, `signing.validity_days`). Erasoft: `CN=Era Soft Labs, OU=Era Soft Labs, O=Era Soft Labs, L=Cochabamba, ST=Cochabamba, C=BO`, alias `Era Soft Labs`, 36.500 días (100 años; Play exige validez hasta después del 22-10-2033). Son **los mismos para todas las apps** de la marca; lo que cambia por app es la clave privada (otro archivo), sus huellas y la contraseña. **Nunca reutilizar la misma clave en varias apps**: una filtración las comprometería todas. Nada personal en el certificado (nombre propio, correo, dirección).
- El alias con espacios funciona (probado: `keytool` lo guarda tal cual y Gradle firma con él), pero va **entre comillas** en `keytool`, `jarsigner` y PEPK.
- `applicationIdSuffix ".debug"`: se mantiene si los escenarios de prueba del debug escriben datos falsos (así no pisan los datos reales de la app de Play); sin sufijo, el debug se instala encima del de Play.

## Paso 1. Bitwarden: crear el ítem y generar la contraseña (antes de crear la clave)

1. Bitwarden → **Nuevo → Inicio de sesión** (*Login*).
2. **Nombre**: `Android · <App> · signing key`. Carpeta: `Android / Keystores` (crearla la primera vez).
3. **Usuario**: el alias (`signing.alias` de `app.json`; Erasoft: `Era Soft Labs`).
4. **Contraseña**: botón **Generar** → 24 caracteres o más, mayúsculas, minúsculas, números y símbolos. Evitar `"`, `'`, `` ` `` y `$` si el generador lo permite (la contraseña pasa por PowerShell y Gradle). **Guardar el ítem ya**, así la contraseña nunca se pierde.
5. Dejar Bitwarden abierto: la contraseña se copia de ahí en el paso 2.

## Paso 2. Crear la clave (ventana aparte)

`appinit.py keystore <repo>` abre PowerShell con `setup-signing.ps1 -Create`. El usuario:
1. Pega la contraseña de Bitwarden dos veces (no se ve al escribir).
2. Confirma los datos del certificado que muestra (los de la marca, de `app.json`); si la marca no tiene, escribe la organización y el país.

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

## Paso 5. Play Console: clave propia en el primer lanzamiento (lo guía `play-console`)

Antes de subir el **primer** AAB (después ya no se puede cambiar sin el proceso de actualización de clave):
1. Play Console → la app → **Prueba y lanzamiento → Integridad de la app → Firma de apps de Google Play** (o el aviso de firma al crear la primera versión) → **Cambiar clave de firma / Change app signing key** → **Exportar y subir una clave de un almacén de claves Java / Export and upload a key from Java keystore**.
2. Descargar **`pepk.jar`** y la **clave pública de cifrado** (`encryption_public_key.pem`) a `D:\Documents\Apps\<App>\KeyStore\pepk\`.
3. En una **ventana de PowerShell aparte** (la contraseña la escribe el usuario, oculta):
   ```powershell
   cd "D:\Documents\Apps\<App>\KeyStore\pepk"
   & "$env:ProgramFiles\Android\Android Studio\jbr\bin\java.exe" -jar pepk.jar --keystore=..\upload.jks --alias="<alias de app.json>" --output=output.zip --include-cert --rsa-aes-encryption --encryption-key-path=encryption_public_key.pem
   ```
   `output.zip` solo lo puede abrir Google: no es un secreto.
4. Subir `output.zip` en esa pantalla. Si Play ofrece registrar **otra clave de subida** (opcional), no hacerlo: la misma clave queda como clave de subida.
5. Subir el primer AAB (`bundleRelease`) a prueba interna.
6. Comprobar en **Integridad de la app → Firma de apps**: el SHA-256 de la **clave de firma de la app** y el de la **clave de subida** son los dos el de `keystore-info.json`. Anotar en `app.json`: `"signing": {"play_app_signing": "own key, verified <fecha>"}`.
- **Google Sign-In / Drive / Firebase**: un solo SHA-1 (el de `keystore-info.json`) para el cliente OAuth y Firebase.
- Si el texto de la pantalla de Play no coincide con estos pasos, leer lo que muestra y seguirlo con el mismo objetivo (clave propia por PEPK); no aceptar la clave generada por Google sin preguntar.

## Otra PC, o una clave que ya existe

1. Restaurar `upload.jks` desde Bitwarden a `D:\Documents\Apps\<App>\KeyStore\`.
2. `appinit.py keystore <repo> --register`: pide alias y contraseña, los comprueba contra la clave y los guarda.

## Proyecto con firma vieja (keystore.properties, contraseñas en el build, otra carpeta)

`references/repo-existente.md`, paso 4. Nunca se crea una clave nueva para una app **ya publicada** sin preguntar: la app publicada se sigue firmando con su clave de subida actual. Si esa clave es la única (app anterior a Play App Signing) o se desconoce cuál es, mirar en Play Console → Integridad de la app qué certificado espera Google y comparar su SHA-256 con el de la clave local (`keytool -list -v`).

## Clave comprometida (contraseña en git, en un chat o en un archivo, o el archivo y la contraseña juntos fuera de lugar)

1. **Subida**: crear una clave de subida nueva (`-Create` con otro archivo, p. ej. `upload-2026.jks`, y `signing.keystore` en `gradle.properties`) y pedir en Play Console → Integridad de la app → **Solicitar restablecimiento de la clave de subida** con su `upload_certificate.pem`. Google tarda unos días.
2. **Firma de la app** (la misma clave en este modelo): Play Console → Integridad de la app → **Actualizar la clave de firma de la app** (una sola vez por app; vale para instalaciones nuevas, las viejas siguen con la anterior). Hacerlo solo si hay sospecha real de que el archivo **y** la contraseña se filtraron.
3. Cambiar la contraseña en Bitwarden y en el Administrador de credenciales de cada PC.
