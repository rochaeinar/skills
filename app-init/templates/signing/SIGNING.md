# Firma de {{APP_NAME}}

Cómo se firma la app **sin contraseñas en texto plano ni en el repo**. Generado por el skill `app-init`.

## La clave

| Qué | Dónde |
|---|---|
| **La clave de la app** (`{{ALIAS}}`, PKCS12, RSA 4096): una sola para todo | `{{KEYSTORE_PATH}}`, **fuera del repo**, en la carpeta de la app |
| Contraseña | Administrador de credenciales de Windows: `{{CREDENTIAL}}` (usuario = alias). Respaldo: Bitwarden |
| Certificado (público, igual en todas las apps de la marca) | `{{DNAME}}`, válido {{VALIDITY}} días. Cada app tiene **su propia** clave privada y contraseña |
| Huellas públicas (SHA-256, SHA-1) y certificado | `keystore-info.json` y `upload_certificate.pem`, junto a la clave |
| En Google Play | La **misma** clave: es la clave de subida y también la clave de firma de la app (Play App Signing con **clave propia**, subida con PEPK en el primer lanzamiento). Google guarda una copia |

- `gradle/signing.gradle` resuelve la firma en este orden: variables `{{ENV_PREFIX}}_STORE_FILE`, `{{ENV_PREFIX}}_KEY_ALIAS`, `{{ENV_PREFIX}}_STORE_PASSWORD`, `{{ENV_PREFIX}}_KEY_PASSWORD` (CI o build manual), luego la credencial de Windows con la clave en `appDataDir` + `signing.keystore` de `gradle.properties`.
- Con la credencial, el release **y el debug** (`signing.signDebug=true`) se firman con esta clave, la misma que firma Google en Play. Así hay un solo SHA-1 (Google Sign-In, Firebase) y un build sin `applicationIdSuffix` se instala encima del de Play sin borrar datos. Sin la credencial, el release sale **sin firmar** (el build lo avisa) y el debug usa la clave de depuración de Android.

## PC nueva

1. Restaurar `{{KEYSTORE}}` desde Bitwarden (adjunto del ítem "Android · {{APP_NAME}} · signing key") a `{{KEYSTORE_PATH}}`.
2. `.\setup-signing.ps1 -Register`: pide el alias y la contraseña (ocultos), los comprueba contra la clave y los guarda en el Administrador de credenciales.
3. `.\gradlew.bat bundleRelease`: no debe avisar `UNSIGNED`.

## Build manual o CI

```powershell
$env:{{ENV_PREFIX}}_STORE_FILE     = "{{KEYSTORE_PATH}}"
$env:{{ENV_PREFIX}}_KEY_ALIAS      = "{{ALIAS}}"
$env:{{ENV_PREFIX}}_STORE_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR((Read-Host "store pw" -AsSecureString)))
.\gradlew.bat clean bundleRelease
Remove-Item Env:{{ENV_PREFIX}}_STORE_PASSWORD
```

## Verificar

```powershell
& "$env:ProgramFiles\Android\Android Studio\jbr\bin\keytool.exe" -list -v -keystore "{{KEYSTORE_PATH}}" -alias "{{ALIAS}}"
```

El SHA-256 debe coincidir con los dos certificados de **Play Console → Prueba y lanzamiento → Integridad de la app → Firma de apps**: el de la clave de firma de la app y el de la clave de subida.

## Reglas

- ❌ Nunca contraseñas en `build.gradle`, `gradle.properties`, `keystore.properties` ni en ningún archivo versionado.
- ❌ Nunca `*.jks` / `*.keystore` en el repo (están en `.gitignore`).
- ✅ Contraseña solo en el Administrador de credenciales (por PC) y en Bitwarden (respaldo).
- ✅ La clave, en 3 lugares: la carpeta de la app, el adjunto de Bitwarden y una copia cifrada sin conexión.
- 🔁 **Si se pierde** (archivo o contraseña): Google tiene una copia y Play sigue firmando; se pide en **Integridad de la app → Solicitar restablecimiento de la clave de subida** con una clave de subida nueva, y los builds locales dejan de instalarse encima del de Play.
- 🚨 **Si se filtra** (archivo + contraseña): es la identidad permanente de la app; con ella se firman APKs que se instalan encima de la tuya fuera de Play. Google solo permite **actualizarla una vez** (Integridad de la app → Actualizar clave de firma de la app; vale para instalaciones nuevas). Por eso: el archivo y la contraseña nunca juntos sin cifrar, nunca por chat ni correo, Bitwarden y Mega con verificación en dos pasos.
