# Configuración de bible-language-ship

Comandos en PowerShell. Es el **paso 4 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md`.

1. **La carpeta principal** `D:\Documents\BibleVersions\Modules\` con su `config.json` (el mismo de todos los skills bible-*; ver `SETUP.md` de bible-language-pack). Este skill usa de él `app_repo`, `play_dir`, `website_site`, `website_slug`, `feature_config`, `bucket` y `credential`; el resto sale de la carpeta (`languages\<idioma>\pack.json` y `ship.json`, `cdn\bible\modules\*.obb`, `_state\`, `idiomas-tracker.md`). Otra carpeta: variable `BIBLE_VERSIONS_CONFIG`.
2. Para las etapas `feature` y `web`: los skills **`play-feature-graphic`** (con su `config.json`) y **`cloudflare-site`** instalados; se buscan por su nombre junto a este skill o en `~\.claude\skills`. El skill **`bugfix`** (del repo de la app) para corregir lo que falle.
3. **Python 3.10+** con Pillow (`pip install pillow`) para las capturas.
4. **Cloudflare** (etapa `cdn`): Node.js (para `npx wrangler@4`) y la credencial `BibleVersions-Cloudflare` en el Administrador de credenciales de Windows (usuario = Account ID, contraseña = token con permiso **Workers R2 Storage: Edit**); la misma que usa `scripts\publish-manifest.ps1` de la app (guía: `scripts\publish-manifest.md` del repo).
5. **Teléfono** para las etapas `tts`, `device_text` y `screenshots`: Android 12 o más nuevo (el idioma de la app se cambia con un enlace de la build debug), depuración USB, Maestro instalado como dice `.maestro\README.md` de la app.
6. Probar: `python $env:USERPROFILE\.claude\skills\bible-language-ship\scripts\ship.py status`.
