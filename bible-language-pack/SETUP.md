# Configuración de bible-language-pack

Comandos en PowerShell.

1. **Python 3.10+** (solo la biblioteca estándar). Comprobar: `python --version`.
2. **Las Biblias descargadas**: `D:\Documents\BibleVersions\BibleVersionsSelected\` con `bibles-manifest.json`. Si faltan: `python D:\Documents\BibleVersions\BibleVersionsSelected\download_bibles.py` (vuelve a descargar las del tracker).
3. **`scripts\config.json`** (por PC, no va al respaldo):
   ```json
   {
     "bibles_dir": "D:/Documents/BibleVersions/BibleVersionsSelected",
     "tracker": "D:/Documents/BibleVersions/idiomas-tracker.md",
     "health_report": "D:/Documents/BibleVersions/healthReport.md",
     "packs_dir": "D:/Documents/BibleVersions/packs",
     "app_repo": "D:/Projects/Android/bible-versions",
     "bucket": "timelesslabs-cdn",
     "credential": "BibleVersions-Cloudflare"
   }
   ```
4. **Solo para `publish`**: Node.js (para `npx wrangler@4`) y la credencial `BibleVersions-Cloudflare` en el Administrador de credenciales de Windows (usuario = Account ID, contraseña = token con permiso **Workers R2 Storage: Edit**). Es la misma que usa `scripts\publish-manifest.ps1` de la app; su guía: `scripts\publish-manifest.md` del repo de la app.
5. Probar: `python $env:USERPROFILE\.claude\skills\bible-language-pack\scripts\pack.py status`.
