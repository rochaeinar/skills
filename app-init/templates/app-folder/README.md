# {{APP_NAME}} (`{{PACKAGE}}`)

Datos de la app que no son código. El repo apunta aquí con `appDataDir` en su `gradle.properties`; `app.json` describe la app para todos los skills.

| Carpeta | Qué va | Quién la usa |
|---|---|---|
| `app.json` | Paquete, repo, firma (sin secretos), librerías, perfiles de Play, Cloudflare y YouTube, web | `app-init` y los demás skills |
| `KeyStore/` | `upload.jks`, `keystore-info.json`, `upload_certificate.pem`. **Respaldada en Bitwarden y en una copia sin conexión** | `gradle/signing.gradle`, `android-release` |
| `Images/icon/` | Ícono y logo (SVG, 512 px de Play) | `play-feature-graphic`, `cloudflare-site` |
| `Images/screens/<idioma>/` | Capturas reales | `play-feature-graphic`, `cloudflare-site`, `play-console` |
| `Images/feature-graphic/`, `Images/promo-video/` | Imagen destacada y videos | `play-feature-graphic`, `app-promo-video` |
| `play/` | Ficha de Play, notas de versión, `play.json` | `play-console`, `android-release` |
| `Docs/` | Evidencias, licencias, documentos de la app | personas |

Nunca contraseñas ni tokens en esta carpeta: están en el Administrador de credenciales de Windows y en Bitwarden.
