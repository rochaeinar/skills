# Aplicar app-init a un repo que ya existe

El objetivo es **ordenar sin romper**: la app puede estar publicada, tener usuarios y una firma que no se puede cambiar. Un paso a la vez, mostrando qué se encontró y qué se propone, y **preguntando todo lo que no sea seguro** (AskUserQuestion). Nunca se regenera el proyecto.

## 0. Antes de tocar nada
- `git status`: si hay cambios sin commit, decírselo al usuario y proponer trabajar en una rama nueva (`chore/app-init`) o esperar a que haga commit. No mezclar el orden con su trabajo.
- `appinit.py detect <repo>` y `profiles`, y leer `CLAUDE.md`, `README`, `SIGNING.md` si existen.
- Presentar un **diagnóstico** con ✅/⚠️/❌ por tema (carpeta de datos, firma, librerías, CLAUDE.md, .claude, .gitignore, remoto) y el plan de los pasos siguientes. Pedir aprobación del plan entero antes del paso 1.

## 1. Paquete y lenguaje
- El paquete **no se toca** (si está publicada, cambiarlo crea otra app). Solo se anota en `app.json`.
- Lenguaje: Java → sigue Java; híbrido → lo nuevo en Kotlin; Kotlin → Kotlin. No se convierte código.

## 2. Carpeta de datos
- `appinit.py candidates "<Nombre>"`: si hay una carpeta fuera de `Apps\`, proponer moverla (`references/carpeta-app.md`, "Mover una carpeta vieja").
- Si no existe, `appdir` la crea. Si las imágenes, la ficha o la clave están en otros lugares (el escritorio, Descargas, dentro del repo), listarlas y preguntar qué se mueve.

## 3. .gitignore y secretos versionados
- `wire` agrega lo que falte. Si `detect` muestra `tracked_secrets` (un `.jks` o `keystore.properties` en git): avisar, `git rm --cached` con permiso, y si alguna vez se subió a un remoto, tratar la contraseña como expuesta (`references/firma.md`, "Clave comprometida").

## 4. Firma
Casos que se encuentran y qué se propone:

| Encontrado | Propuesta |
|---|---|
| Ya lee del Administrador de credenciales (patrón `readCredential` en el build) | Funciona: se puede dejar. Opcional: pasar a `gradle/signing.gradle` (mismo resultado, el build queda más corto). Si la clave está fuera de `Apps\`, solo cambiar la ruta. |
| `keystore.properties` con contraseñas en texto plano | Pasar las contraseñas al Administrador de credenciales (`setup-signing.ps1 -Register`), cambiar a `signing.gradle`, y **borrar** `keystore.properties` (con permiso, después de comprobar que el build firma). |
| Contraseñas dentro de `build.gradle` | Igual que arriba, y revisar si están en el historial de git. |
| Release firmado con la clave de debug (sin clave aún) | Si la app **nunca se subió a Play**: crear la clave de subida (`references/firma.md` desde el paso 1). Si ya se subió, averiguar con qué clave (Play Console → Integridad de la app) antes de nada. |
| Sin ninguna firma | Como app nueva. |

Pasos para migrar a `signing.gradle`:
1. `appinit.py wire <repo> --app-dir <carpeta>` (plan → `--yes`): agrega el script y el `apply` al final del build de la app.
2. Quitar con Edit el bloque viejo (`readCredential`, `resolveReleaseSigning`, `signingConfigs`, y el `signingConfig` de los `buildTypes`). Si el debug tenía `applicationIdSuffix`, se mantiene.
3. Si la credencial vieja tiene otro nombre (p. ej. `bibleversions-release-signing`), poner ese nombre en `signing.credential` en lugar de crear otra. Así no cambia nada en la PC.
4. `gradlew bundleRelease` + `jarsigner -verify`, y comparar el SHA-256 del certificado con el de Play (`keytool -printcert -jarfile app-release.aab`).

## 5. Librerías
- Las que ya usa, se dejan como están (fuente o JitPack). Si usa JitPack y el usuario quiere depurar: proponer pasar a módulos de fuente, no hacerlo de oficio.
- Si usa otra cosa (Room, Timber), **no se migra**: se anota y se pregunta si quiere un plan aparte.

## 6. CLAUDE.md y .claude
- Sin `CLAUDE.md`: el base (`wire` lo escribe) y completar las secciones `FILL` leyendo el código.
- Con `CLAUDE.md`: comparar con `templates/claude/CLAUDE.md` y proponer **solo las reglas que faltan** (carpeta de datos, firma, regla de bugs con test, reglas de librerías, adb, credenciales y git) como una lista; agregar las aprobadas en su sección. No reescribir lo que el usuario escribió.
- `.claude/settings.json`: crearlo si falta; si existe, proponer las entradas que faltan.

## 7. Perfiles, remoto, resumen
- Perfiles: preguntar cuál usa hoy (si ya publica en Play, el perfil de esa cuenta) y `play.py register` si la app no está en `apps.json`.
- Remoto: si ya tiene, se deja. Si no, `bitbucket create`.
- `check` y `summary`. Los cambios quedan **sin commit**; proponer el mensaje del commit y hacerlo solo si el usuario lo pide.
