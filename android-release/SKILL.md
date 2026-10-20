---
name: android-release
description: Publica una versión nueva de una app Android en Google Play de punta a punta - calcula la versión siguiente (versionName = fecha de hoy, versionCode = uno más que todo lo que Play ya tiene, verificado contra Play), la escribe en build.gradle, corre los tests, genera el AAB release firmado, prepara las notas de versión por idioma y lo publica con el skill play-console (producción, prueba interna/cerrada/abierta, al 100 % o escalonado). Úsalo cuando pidan "publicar una versión nueva", "subir la app a producción", "hacer release", "build release y publicar", "incrementar la versión" o "sacar una actualización".
---

# Release de una app Android a Google Play

Requiere el skill **`play-console`** ya configurado para la app (su `SETUP.md`: cuenta de servicio, `auth`, `register`) y la **firma release** del proyecto (clave de subida). Configuración: `SETUP.md`.

Todo pasa por `scripts/release.py` (con `python`, **sin `-I`**), ejecutado **desde la raíz del proyecto Android** (o `--project <carpeta>`). Encuentra la carpeta de datos de Play como `play-console` (applicationId → `apps.json`, o `--app <carpeta>`).

## Pasos

1. **`release.py plan`**: muestra la versión local, todas las versiones en Play (cada pista y todo AAB subido alguna vez), la versión propuesta, si faltan notas, los commits desde el último cambio de versión y si hay cambios sin commit. No cambia nada.
   - **versionCode** = máximo(local, el más alto que Play vio alguna vez) + 1. Un código subido una vez nunca se puede reutilizar, aunque esa versión se haya detenido.
   - **versionName** = fecha de hoy con el formato de la versión actual (`26.10.15` → `%y.%m.%d`). Si ya hubo un release hoy: `26.10.19.2`.
2. **`release.py bump`**: escribe la versión en `<módulo>/build.gradle(.kts)` (respeta los fines de línea). Se niega si hay otros cambios sin commit (irían al build sin estar en git), salvo `--allow-dirty`.
3. **`release.py build`**: corre los tests unitarios (`test_task`) y `bundleRelease`, y verifica que el AAB sea nuevo y **esté firmado**. Tarda varios minutos: ejecutarlo en segundo plano. `--skip-tests` solo si el usuario lo pide.
4. **Notas de versión**: `<datos>/changelogs/<lang>/<versionCode>.txt` para **cada idioma** de la ficha (máx. 500 caracteres). Redactarlas a partir de los commits que lista `plan`, solo con cambios visibles para el usuario, con el estilo de las anteriores (emojis, una línea por cambio). **Mostrarlas al usuario** antes de publicar.
5. **`release.py publish --track production --rollout 1`** (sin `--yes`): sube el AAB a una edición, comprueba que su versionCode sea el esperado, Google la valida y se descarta. Mostrar el resultado y **pedir confirmación**.
6. **`release.py publish ... --yes`**: publica. Luego `play.py status` para confirmarlo.
7. **Commit** del cambio de versión en el repo de la app, con el estilo del repo (p. ej. `Bump version to 26.10.19 (17)`). Push solo si el usuario lo pide.

## Reglas

- **Producción** solo cuando el usuario lo pide explícitamente; el porcentaje es el que pida (`--rollout 1` = 100 %, `0.1` = 10 %). Si no dice, proponer prueba interna o escalonado.
- **Nunca `--yes` sin que el usuario haya visto** la versión, las notas y el resultado del ensayo.
- Si un paso falla (tests, firma, validación de Google), parar y explicar; no saltarse controles.
- Un AAB subido "gasta" su versionCode aunque no se publique: si hay que rehacer el build después de subirlo, hacer `bump` otra vez.

## Configuración por app (opcional)

En el `play.json` de la app (carpeta de datos de `play-console`), todo con valores por defecto:

```json
"release": {
  "module": "app",
  "version_name": "%y.%m.%d",
  "test_task": ":app:testDebugUnitTest"
}
```

`test_task: ""` no corre tests. `version_name` es un formato de `strftime`; sin él se deduce de la versión actual (`yy.MM.dd`, `yyyy.MM.dd`, `yyyyMMdd`), y si no es una fecha pide configurarlo.

## Errores frecuentes

| Error | Causa |
|---|---|
| "expected one literal versionCode and versionName" | La versión está en variables, `gradle.properties` o *flavors*: no soportado, cambiarla a mano y usar solo `build`/`publish` |
| "is not signed" | Gradle no encontró la clave de subida (el build avisa `UNSIGNED`): revisar la configuración de firma del proyecto |
| "versionCode N is not above Play's" | Falta `bump`, o ese código ya se subió antes (aunque no se publicara) |
| "The bundle has versionCode X, expected Y" | El AAB es de un build anterior: `build` otra vez |
| "No release notes for N" | Faltan `changelogs/<lang>/N.txt` para esos idiomas |
| HTTP 403 al publicar en producción | La cuenta de servicio no tiene el permiso **Publicar en producción** (`play-console/SETUP.md` paso 3) |

## Archivos

- `scripts/release.py` (importa `../play-console/scripts/play.py`), `SETUP.md`.
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
