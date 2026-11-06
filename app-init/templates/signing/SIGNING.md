# Firma de {{APP_NAME}}

Cómo se firma la app **sin contraseñas en texto plano ni en el repo**. Generado por el skill `app-init`.

## La clave

| Qué | Dónde |
|---|---|
| Clave de subida (`{{ALIAS}}`, PKCS12, RSA 4096) | `{{KEYSTORE_PATH}}`, **fuera del repo**, en la carpeta de la app |
| Contraseña | Administrador de credenciales de Windows: `{{CREDENTIAL}}` (usuario = alias). Respaldo: Bitwarden |
| Huellas públicas (SHA-256, SHA-1) y certificado | `keystore-info.json` y `upload_certificate.pem`, junto a la clave |
| Clave de firma de la app | La guarda Google (**Play App Signing**). La nuestra es solo la de **subida** |

- `gradle/signing.gradle` resuelve la firma en este orden: variables `{{ENV_PREFIX}}_STORE_FILE`, `{{ENV_PREFIX}}_KEY_ALIAS`, `{{ENV_PREFIX}}_STORE_PASSWORD`, `{{ENV_PREFIX}}_KEY_PASSWORD` (CI o build manual), luego la credencial de Windows con la clave en `appDataDir` + `signing.keystore` de `gradle.properties`.
- Con la credencial, el release se firma con la clave de subida, y también el debug si `signing.signDebug=true`. Así el inicio de sesión de Google funciona y se puede instalar el debug encima del de Play. Sin la credencial, el release sale **sin firmar** (el build lo avisa) y el debug usa la clave de depuración de Android.

## PC nueva

1. Restaurar `{{KEYSTORE}}` desde Bitwarden (adjunto del ítem "Android · {{APP_NAME}} · upload key") a `{{KEYSTORE_PATH}}`.
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
& "$env:ProgramFiles\Android\Android Studio\jbr\bin\keytool.exe" -list -v -keystore "{{KEYSTORE_PATH}}" -alias {{ALIAS}}
```

El SHA-256 debe coincidir con el de **Play Console → Prueba y lanzamiento → Integridad de la app → Firma de apps → Certificado de clave de subida**.

## Reglas

- ❌ Nunca contraseñas en `build.gradle`, `gradle.properties`, `keystore.properties` ni en ningún archivo versionado.
- ❌ Nunca `*.jks` / `*.keystore` en el repo (están en `.gitignore`).
- ✅ Contraseña solo en el Administrador de credenciales (por PC) y en Bitwarden (respaldo).
- ✅ La clave, en 3 lugares: la carpeta de la app, el adjunto de Bitwarden y una copia cifrada sin conexión.
- 🔁 Si se pierde o se filtra la clave de subida: **Play Console → Integridad de la app → Solicitar restablecimiento de la clave de subida**, con un `upload_certificate.pem` nuevo. Para eso existe Play App Signing.
