# Configuración de bible-language-ship

Comandos en PowerShell.

1. Los skills **`bible-language-pack`**, **`play-feature-graphic`** (con su `config.json`), **`cloudflare-site`** y **`bugfix`** (del repo de la app) instalados.
2. **Python 3.10+** con Pillow (`pip install pillow`) para las capturas.
3. **`scripts\config.json`** (por PC, no va al respaldo):
   ```json
   {
     "app_repo": "D:/Projects/Android/bible-versions",
     "packs_dir": "D:/Documents/BibleVersions/packs",
     "play_dir": "D:/Documents/BibleVersions/play",
     "website_site": "D:/Projects/websites/sites/bibleversions",
     "website_slug": "bibleversions",
     "tracker": "D:/Documents/BibleVersions/idiomas-tracker.md",
     "pack_script": "C:/Users/<usuario>/.claude/skills/bible-language-pack/scripts/pack.py",
     "web_script": "C:/Users/<usuario>/.claude/skills/cloudflare-site/scripts/web.py",
     "feature_config": "D:/Documents/BibleVersions/Images/feature-graphic/feature-graphic.json",
     "feature_script": "C:/Users/<usuario>/.claude/skills/play-feature-graphic/scripts/build_feature_graphic.py"
   }
   ```
4. **Cloudflare**: la credencial `BibleVersions-Cloudflare` (ver `scripts\publish-manifest.md` del repo de la app).
5. **Teléfono** para las etapas `tts`, `device_text` y `screenshots`: Android 12 o más nuevo (el idioma de la app se cambia con un enlace de la build debug), depuración USB, Maestro instalado como dice `.maestro\README.md` de la app.
6. Probar: `python $env:USERPROFILE\.claude\skills\bible-language-ship\scripts\ship.py status`.
