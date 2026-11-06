---
name: app-init
description: Inicializa una app Android nueva o pone en orden una existente, para que todos los demás skills fluyan después - la carpeta de datos de la app en D:\Documents\Apps\<App>\ (KeyStore, Images, play, Docs) con su app.json y la referencia desde el repo, el certificado de subida para Google Play creado y guardado sin contraseñas en disco (Administrador de credenciales de Windows, guía paso a paso para respaldarlo en Bitwarden), la firma en Gradle igual para Groovy y Kotlin DSL, el proyecto base en Kotlin + Compose (o seguir en Java si el proyecto es Java), las librerías propias (data-access, RestLog4Android, synchronizer, custom-ads), CLAUDE.md y .claude con las reglas comunes, la marca y el paquete (com.erasoft, com.timeless o propio), los perfiles de Play Console, Cloudflare y YouTube, y el repo en Bitbucket creado por la API; termina con un resumen. Úsalo cuando pidan "inicializar una app", "crear una app nueva", "configurar el certificado / keystore / firma", "app-init", "ordenar este proyecto", "preparar la app para Play" o "crear el repo en Bitbucket".
---

# Inicializar una app (app-init)

Es uno de los primeros skills del ciclo de una app: deja todo en su lugar para que los demás no tengan que adivinar. **No genera desorden**: cada paso muestra su plan, y nada se escribe, mueve ni crea sin `--yes` y sin que el usuario lo haya visto. En un proyecto existente, **todo lo dudoso se pregunta antes de actuar**.

Una vez por PC: `SETUP.md` (CredentialManager, Bitwarden, token de Bitbucket).

Todo pasa por `scripts/appinit.py` (con `python`). Lo que no hace el script lo hace Claude con Edit, siguiendo las referencias:

| Referencia | Cuándo |
|---|---|
| `references/carpeta-app.md` | Pasos 2-3: la carpeta `D:\Documents\Apps\<App>\`, `app.json`, mover carpetas viejas |
| `references/firma.md` | Paso 6: certificado de subida, Play App Signing, Bitwarden paso a paso |
| `references/librerias.md` | Paso 5: librerías por defecto, cuándo incluir cada una, cómo extenderlas |
| `references/repo-existente.md` | Repo que ya existe: ordenar paso a paso |
| `references/buenas-practicas.md` | Paso 7: de dónde salen las reglas del `CLAUDE.md` base |
| `references/flujo-skills.md` | Pasos 8 y 10: qué deja listo cada paso para los demás skills |

## Flujo

### 0. Detectar (sin preguntar)
- `appinit.py detect <repo>`: lenguaje (cuenta `.java`/`.kt`), DSL de Gradle, paquete, Compose, librerías incluidas, firma actual (y contraseñas en texto plano), CLAUDE.md, `.claude/`, Maestro, git y remoto, carpeta de datos enlazada, claves versionadas.
- `appinit.py profiles`: perfiles de Play (`PlayConsole@<perfil>`), Cloudflare (`CloudflarePages@<perfil>` y sus zonas), YouTube y si hay token de Bitbucket.
- `appinit.py candidates "<Nombre>"`: carpetas de `D:\Documents` que pueden ser de esta app (p. ej. `D:\Documents\BibleVersions`).
- Mostrar el resultado en ✅/⚠️/❌ con lo que falta.

### 1. Preguntar solo lo que falta (AskUserQuestion, una sola ronda)
1. **Nombre** de la app y **marca** → paquete: `com.erasoft.<app>` (web en `era-soft.app`), `com.timeless.<app>` (web en `timelesslabs.app`) o propio. Recomendar la marca que ya usan los perfiles. El paquete **no se cambia nunca** después de publicar: confirmarlo.
2. **Lenguaje** (solo si es nuevo): Kotlin + Compose por defecto. Un proyecto Java sigue en Java; uno híbrido escribe lo nuevo en Kotlin. No se pregunta si ya está claro.
3. **Librerías**: `dal` y `restlog` por defecto; `synchronizer` si respalda o sincroniza en Drive; `custom-ads` si muestra anuncios propios (`references/librerias.md`).
4. **Perfiles** (solo la configuración inicial, nada se publica): Play Console, Cloudflare y YouTube de la lista de `profiles`. Si la cuenta de Play es nueva y no tiene perfil, se anota y se configura con el `SETUP.md` de `play-console`.
5. **Repo**: crear en Bitbucket (workspace, proyecto, privado) o dejar el remoto que ya tiene.
6. Si hay una carpeta de datos fuera de `Apps\`: **¿moverla?** (paso 3).

### 2. Carpeta de la app
`appinit.py appdir "D:/Documents/Apps/<App>" --name "<Nombre>" --package <id> --brand <marca> --libs dal,restlog --play-profile <p> --cloudflare-profile <p> --youtube-profile <p> [--domain <sub.zona>]` → plan → `--yes`. Crea `KeyStore/`, `Images/`, `play/`, `Docs/`, `README.md` y **`app.json`** (un archivo de configuración por app, sin secretos). Esquema y reglas: `references/carpeta-app.md`.

### 3. Mover lo que ya existe (si aplica)
Una carpeta como `D:\Documents\BibleVersions` se mueve a `D:\Documents\Apps\BibleVersions` **solo con el permiso del usuario**:
1. `appinit.py refs "<carpeta vieja>" --repo <repo>` lista cada archivo que la nombra (build, `apps.json` de play-console, `site.json` de la web, `video.json`, `feature-graphic.json`, scripts).
2. Mostrar la lista y el plan (mover, y cambiar cada referencia). Pedir confirmación.
3. Mover (`Move-Item`, misma unidad: es instantáneo y no copia), cambiar las referencias con Edit, volver a correr `refs` (debe quedar vacío) y comprobar que el build sigue firmando.

### 4. Proyecto
- **Nuevo**: `appinit.py scaffold <repo> --app-dir <carpeta> --name "<Nombre>" --package <id> --libs dal,restlog` → plan → `--yes`. Kotlin + Compose + Material 3, catálogo de versiones, idioma por app, release con R8, test de JVM, el *wrapper* de Gradle del proyecto local más nuevo y `local.properties`. **Antes del primer build**, actualizar `gradle/libs.versions.toml` a las versiones estables actuales (se verifican en línea, no de memoria).
- **Existente**: no se regenera nada; seguir `references/repo-existente.md`.

### 5. Librerías propias
Nuevo: ya incluidas por `scaffold`. Existente: agregar los `include` en `settings.gradle(.kts)` y `implementation(project(":x"))` con Edit (`references/librerias.md`), con las dependencias entre ellas (`restlog` y `synchronizer` necesitan `:dal`).

### 6. Firma (certificado de subida)
1. `appinit.py wire <repo> --app-dir <carpeta>` → plan → `--yes`: `gradle/signing.gradle` (sirve igual para Groovy y Kotlin DSL), `setup-signing.ps1`, `SIGNING.md`, los nombres en `gradle.properties` (`appDataDir` = la referencia a la carpeta de la app), `.gitignore`, `CLAUDE.md` si falta y `.claude/settings.json`.
2. **Primera vez: guiar paso a paso con `references/firma.md`** (Bitwarden primero, luego `appinit.py keystore <repo>` abre una ventana aparte donde el usuario escribe la contraseña oculta; luego el respaldo). Nunca pedir ni mostrar una contraseña en el chat.
3. Clave existente (otra PC, restaurada de Bitwarden): `appinit.py keystore <repo> --register`.
4. Verificar: `gradlew bundleRelease` sin `UNSIGNED` y `jarsigner -verify` del AAB.

### 7. Claude Code
- `CLAUDE.md`: el base de `templates/claude/CLAUDE.md` (lo escribe `wire` si falta). Completar las secciones `FILL` con lo que se sabe del proyecto. Si ya existe, **no se reemplaza**: proponer las reglas que le faltan y agregarlas con permiso.
- `.claude/settings.json`: permisos compartidos (gradle, git de lectura) y `deny` de lectura de `*.jks`. `settings.local.json` queda personal e ignorado por git.
- Skills del proyecto (`.claude/skills/`): no se crean; si el proyecto tiene, se dejan.

### 8. Perfiles
- Play: `python ~/.claude/skills/play-console/scripts/play.py register "<carpeta>/play" --package <id> --profile <perfil>` (solo local: crea `play.json` y registra la app en esta PC; no llama a Google).
- Cloudflare y YouTube: quedan en `app.json` (`profiles`); `cloudflare-site new` y `app-promo-video` (`"youtube_profile"` en `video.json`) los toman de ahí cuando se usen. No se crea el sitio ni el video aquí.

### 9. Repo en Bitbucket
- Token una vez por PC: `SETUP.md` (Bitbucket). `appinit.py bitbucket check` lo comprueba y lista los workspaces.
- `appinit.py bitbucket create <repo> --workspace <ws> --slug <nombre> [--project <KEY>]` → plan → `--yes`: crea el repo **privado** por la API (o reutiliza el que existe), hace `git init` si falta y agrega `origin`. **No hace commit ni push**: eso solo si el usuario lo pide (primer commit: revisar `git status` para que no entre nada de `.gitignore`).

### 10. Resumen (siempre al final)
`appinit.py check <repo>` (OK/WARN/FAIL) y `appinit.py summary <repo>` → mostrar el resumen en Markdown: paquete, lenguaje, repo y remoto, carpeta de la app, firma (alias, credencial, SHA-256), librerías, perfiles, web, controles pendientes y **los siguientes skills en orden** (`templates/next-steps.md`). Cada ⚠️ con su cómo resolverlo.

## Reglas
- **Nada sin plan y sin `--yes`**; mover, borrar o reemplazar, siempre con el permiso explícito del usuario.
- **Secretos**: nunca en el chat, el repo ni archivos. Solo en el Administrador de credenciales (por PC, escritos en una ventana aparte) y en Bitwarden (respaldo). `gradle.properties` y `app.json` guardan nombres, nunca contraseñas.
- La clave (`*.jks`) vive solo en `D:\Documents\Apps\<App>\KeyStore\`, en Bitwarden y en una copia sin conexión. `setup-signing.ps1 -Create` nunca sobrescribe una clave.
- Un `*.jks` o `keystore.properties` versionado en git: avisar y proponer cómo sacarlo (y si la contraseña estuvo expuesta, tratar la clave como comprometida: `references/firma.md`).
- Paquete: definitivo después del primer AAB subido. Preguntar dos veces si hay duda.
- Commit y push solo si el usuario lo pide. En los repos de las librerías, nunca sin permiso.
- El skill no conoce ningún proyecto concreto: todo sale de `detect`, de `app.json` y de las plantillas.

## Archivos
- `scripts/appinit.py`: `detect`, `profiles`, `candidates`, `refs`, `appdir`, `scaffold`, `wire`, `keystore`, `bitbucket`, `check`, `summary`.
- `templates/signing/`: `signing.gradle`, `setup-signing.ps1`, `SIGNING.md`. `templates/claude/`: `CLAUDE.md`, `settings.json`. `templates/project-kotlin/`: el proyecto base. `templates/app-folder/README.md`, `templates/next-steps.md`.
- Respaldo central de todos los skills: `D:/Projects/skills/` (con historial git). Después de cambiar el skill, copiarlo ahí; no hacer copias en otros lugares.
