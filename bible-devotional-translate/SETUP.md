# Configuración de bible-devotional-translate

Comandos en PowerShell.

1. **Python 3.10+** (solo la biblioteca estándar). Comprobar: `python --version`.
2. **Los datos de Bible Versions** en `D:\Documents\BibleVersions\`: `BibleVersionsSelected\ES-Spanish\coffee_es.dev` (el original) y `reina-valera-1960.bblx`, `BibleVersionsSelected\EN-English\coffee_en.dev`, los paquetes de `packs\` (skill `bible-language-pack`) y los `.obb` publicados en `cdn\bible\modules\`.
3. **El repo de la app** (`D:\Projects\Android\bible-versions`): `cdn/bible/module-ids.json`, `cdn/bible/manifest.json` y `app/src/main/assets/languages.json`.
4. **`scripts\config.json`** (por PC, no va al respaldo):
   ```json
   {
     "bibles_dir": "D:/Documents/BibleVersions/BibleVersionsSelected",
     "packs_dir": "D:/Documents/BibleVersions/packs",
     "work_dir": "D:/Documents/BibleVersions/devotional",
     "cdn_dir": "D:/Documents/BibleVersions/cdn/bible",
     "app_repo": "D:/Projects/Android/bible-versions"
   }
   ```
5. **`pack.py` del skill `bible-language-pack`** con soporte de `local_modules` (copia `packs\<idioma>\modules\*` al armar el paquete). Viene en el respaldo desde 2026-10-22.
6. Probar: `python $env:USERPROFILE\.claude\skills\bible-devotional-translate\scripts\coffee.py status`.

Publicar (subir a R2 y el manifiesto) usa la credencial `BibleVersions-Cloudflare` del skill `bible-language-pack` y `scripts\publish-manifest.ps1` de la app.
