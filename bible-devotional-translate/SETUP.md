# Configuración de bible-devotional-translate

Comandos en PowerShell. Es el **paso 3 de 5** del flujo de `D:\Documents\BibleVersions\Modules\README.md`.

1. **Python 3.10+** (solo la biblioteca estándar). Comprobar: `python --version`.
2. **La carpeta principal** `D:\Documents\BibleVersions\Modules\` con su `config.json` (el mismo de todos los skills bible-*; ver `SETUP.md` de bible-language-pack). De ella usa:
   - `common\es\coffee_es.dev` (el original), `common\en\coffee_en.dev` (apoyo y módulo inglés), `languages\es\modules\reina-valera-1960.bblx`, `languages\en\modules\king-james-version.bblx`;
   - por idioma: `languages\<idioma>\pack.json`, la Biblia en `modules\`, el estado en `devotional\` y el resultado `modules\coffee_<idioma>.dev`;
   - `cdn\bible\modules\*.obb` (solo `integrate`, para comprobar que el paquete trae la reflexión).

   Otra carpeta (pruebas): variable `BIBLE_VERSIONS_CONFIG`.
3. **El repo de la app** (`app_repo` del `config.json`): `cdn/bible/module-ids.json` y `app/src/main/assets/languages.json`.
4. Probar: `python $env:USERPROFILE\.claude\skills\bible-devotional-translate\scripts\coffee.py status`.

Este skill no arma ni sube paquetes: después de `coffee.py build`, `pack.py build <idioma>` (bible-language-pack, también `en`, `es`, `es-lite`) y `ship.py cdn <idioma>` (bible-language-ship).
