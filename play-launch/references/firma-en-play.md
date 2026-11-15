# Firma en Google Play: una sola clave para todo (hallazgos verificados 2026-11-14)

El modelo de las apps del usuario (skill `app-init`): **una sola clave por app** firma el debug, el release, la subida a Play y lo que Play entrega a los usuarios. Huella SHA-256 en `app.json` → `signing.sha256`.

## Lo que hace Play por defecto (y por qué hay que cambiarlo)

- **Una app nueva queda inscrita automáticamente en la firma híbrida "quantum-ready" con claves generadas por Google** (RSA 4096 clásica + ML-DSA-65 post-cuántica). Si no se hace nada, Play firma lo que entrega con una clave de Google, distinta de la nuestra.
- **Dónde se cambia:** *Protected with Play* (Protegido con Play) > *Play Store protection* > **Manage Play app signing** (Administrar la firma de apps de Play) > **Change key** (Cambiar clave) > proporcionar una copia de la clave propia (PEPK, cifrada con la clave pública de Google; la contraseña la escribe el usuario en una ventana aparte, ver `app-init/references/firma.md` paso 5).
- **Cuándo:** se puede cambiar **solo antes de que una versión llegue a prueba abierta o producción**. Hacerlo **justo después de crear la app y antes del primer AAB**, para que ninguna versión se firme con la clave de Google.
- **Después ya no se cambia**, solo se puede pedir una *actualización de clave* (una vez al año, para Android 17+), que cambia el certificado.
- La firma híbrida usa un bloque de firma 3.2 que verifican los dispositivos con **Android 17 (API 37)+**; en ese caso Play registra tres claves (clásica nueva, PQC y la clásica para dispositivos viejos). Si la pantalla de *Change key* no deja usar la clave propia como **única** clave clásica (es decir, si ofrece mantener la híbrida con una clásica nueva generada por Google), **detenerse y preguntar al usuario**: en Android 17+ el certificado ya no sería el mismo que el del debug y del release local, y un release local no podría instalarse encima del de Play en esos teléfonos.

## Lo que se ve en la consola (Era Soft Labs, es-419, 2026-11-15)

1. Recién creada, la app ya tiene **clave de firma generada por Google** ("Disponible para criptografía cuántica (beta)"), con huella distinta de la propia. Es lo esperado.
2. Camino: **Protegido con Play** → sección **Protección de Play Store** → *Mostrar detalles* → **Administrar la firma de apps de Play** (`/app/<id>/keymanagement`, página "Firma de apps") → **Cambiar clave**.
3. Aviso: cambiarla deja sin actualizaciones a los testers internos/cerrados que ya la instalaron y obliga a volver a subir las versiones. **Sin versiones ni testers todavía no afecta**: por eso se hace antes del primer AAB.
4. "Preferencias de firma de apps", cuatro opciones: *Permite que Google administre… (recomendado) – criptografía cuántica* (por defecto) · *Usar la misma clave que otra app de esta cuenta* · **Exportar y subir una clave desde un almacén de claves Java** · *Exportar y subir una clave (sin almacén Java)*. La tercera es la del modelo de una sola clave: **no** es híbrida (no dice criptografía cuántica), así que el certificado es el propio en todos los teléfonos.
5. Con esa opción: *Descargar clave pública de encriptación* y *Descargar herramienta PEPK* (Claude los baja a `KeyStore/pepk/` con Playwright), comando `java -jar pepk.jar --keystore=upload.jks --alias="<alias>" --output=output.zip --include-cert --rsa-aes-encryption --encryption-key-path=encryption_public_key.pem` (Claude abre una ventana de PowerShell aparte con el comando listo; el usuario solo escribe la contraseña dos veces), *Subir archivo ZIP generado*, y **Guardar**. La "nueva clave de carga" opcional **no** se crea (modelo de una sola clave).

## Protección automática (el recuadro de "Crear app")

- "Obtendrás protección automática: se agregará una verificación del instalador al código de tu app" = **automatic protection / installer check**. Play **modifica el código** de las APK que entrega (verifica al abrir que la app vino de Google Play; si no, invita a bajarla de Play) y las **vuelve a firmar con la clave de firma de la app**.
- **No cambia el certificado**: si la clave de firma de la app es la nuestra, lo entregado sigue firmado con la nuestra. El certificado lo decide solo la página de *Play app signing* (arriba).
- Requisitos: Play App Signing, AAB y minSdk ≥ 24. Las compilaciones locales (debug y release instaladas por adb) no llevan la protección. *Internal app sharing* tampoco.
- Incompatible con *code transparency* y con la librería de licencias de Play; se puede desactivar por versión (*App bundle enhancements* de la versión > *Turn off protection for this release*).
- Se deja activada salvo que el usuario diga lo contrario; anotarlo en el resumen de la etapa 3.

## Verificación obligatoria (fail-closed)

1. En la página *Manage Play app signing*, la huella SHA-256 de la **clave de firma de la app** y la de la **clave de subida** deben ser iguales a `app.json` → `signing.sha256`. Captura en `launch/evidence/`.
2. Después del primer AAB procesado: `launch.py verify-signing --version-code <N>` compara el certificado de las APK que genera Play (API `generatedapks`) con la clave propia. Si no coincide, **no** pasar a prueba abierta ni producción: arreglarlo en *Play app signing* mientras todavía se puede.
3. En el teléfono, instalar la versión de Play y comprobar `apksigner verify --print-certs` sobre la APK descargada desde *App bundle explorer* (opcional, cuando haya dudas).

## Fuentes

- Use Play App Signing: https://support.google.com/googleplay/android-developer/answer/9842756
- Automatic protection: https://support.google.com/googleplay/android-developer/answer/10183279
- Installer check: https://support.google.com/googleplay/android-developer/answer/15621622
- Post-quantum en Android: https://blog.google/security/security-for-the-quantum-era-implementing-post-quantum-cryptography-in-android/
