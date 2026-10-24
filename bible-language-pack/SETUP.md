# Configuración de bible-language-pack

Comandos en PowerShell. Es el **paso 2 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md`.

1. **Python 3.10+** (solo la biblioteca estándar). Comprobar: `python --version`.
2. **La carpeta principal** `D:\Documents\BibleVersions\Modules\` con su **`config.json`** (uno solo para los skills bible-*; no va en el skill ni en el respaldo):
   ```json
   {
     "app_repo": "D:/Projects/Android/bible-versions",
     "bucket": "timelesslabs-cdn",
     "credential": "BibleVersions-Cloudflare",
     "play_dir": "D:/Documents/BibleVersions/play",
     "website_site": "D:/Projects/websites/sites/bibleversions",
     "website_slug": "bibleversions",
     "feature_config": "D:/Documents/BibleVersions/Images/feature-graphic/feature-graphic.json"
   }
   ```
   Todo lo demás se deriva de la carpeta del `config.json`: `languages\`, `common\`, `cdn\bible\`, `_cache\`, `idiomas-tracker.md`, `healthReport.md`. Otra carpeta (pruebas): variable `BIBLE_VERSIONS_CONFIG` con la ruta de otro `config.json`.
3. **Las Biblias descargadas** en `Modules\languages\<idioma>\sources\`, registradas en `Modules\languages\manifest.json`. Las baja el skill **bible-download** (paso 1).
4. **7-Zip** (opcional, `C:\Program Files\7-Zip\7z.exe`): el `.obb` sale ~5 % más chico, igual que los ya publicados. Sin él se usa zlib nivel 9.
5. Probar: `python $env:USERPROFILE\.claude\skills\bible-language-pack\scripts\pack.py status`.

Subir el `.obb` a R2 ya no es de este skill: lo hace `ship.py cdn` (bible-language-ship, paso 4).
