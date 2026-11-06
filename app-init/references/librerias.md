# Librerías propias por defecto

Son la opción por defecto en toda app nueva. Room, Timber, otro sync u otro sistema de anuncios solo si el proyecto ya los usa o el usuario lo decide. La guía de uso detallada (arquitectura, seguridad de los logs, sync detrás de un puerto) está en `~/.claude/skills/app-design-implementation/references/librerias-propias.md`: no se duplica aquí.

| Librería | Módulo | Fuente | Paquete | Incluirla cuando | Repo |
|---|---|---|---|---|---|
| data-access (DAL) | `:dal` | `D:/Projects/Android/data-access/DataAccessLayer/dal` | `com.erc.dal` | Siempre que haya datos locales (SQLite) | GitHub, JitPack `com.github.rochaeinar:data-access` |
| RestLog4Android | `:restlog` | `D:/Projects/Android/RestLog4Android/RestLog` | `com.erc.log` | Siempre (logs); **necesita `:dal`** | GitHub, JitPack `com.github.rochaeinar:RestLog4Android` |
| synchronizer | `:synchronizer` | `D:/Projects/Android/synchronizer/app` | `com.erasoft.synchronizer` | Respaldo o sincronización en Google Drive; **necesita `:dal`** (lo usa como `compileOnly`) | Bitbucket |
| custom-ads | `:custom-ads` | `D:/Projects/Android/custom-ads` | `com.erc.customads` | Anuncios intersticiales propios (WebView), solos o junto a AdMob | Bitbucket |

Antes de usarlas, leer su `README.md` / `CLAUDE.md` / `IMPLEMENTATION_NOTES.md` y su API real (cambian).

## Cómo se incluyen

Como módulos de código fuente (así lo hacen todas las apps), para depurar y corregir en la propia librería:

```kotlin
// settings.gradle.kts
include(":dal")
project(":dal").projectDir = file("D:/Projects/Android/data-access/DataAccessLayer/dal")
include(":restlog")
project(":restlog").projectDir = file("D:/Projects/Android/RestLog4Android/RestLog")
include(":synchronizer")
project(":synchronizer").projectDir = file("D:/Projects/Android/synchronizer/app")
include(":custom-ads")
project(":custom-ads").projectDir = file("D:/Projects/Android/custom-ads")
```

```groovy
// settings.gradle (Groovy)
include ':dal'
project(':dal').projectDir = new File('D:/Projects/Android/data-access/DataAccessLayer/dal')
```

```kotlin
// app/build.gradle.kts
implementation(project(":dal"))
implementation(project(":restlog"))
```

Detalles que rompen el build si se olvidan:
- **synchronizer** aplica AGP con `alias(libs.plugins.android.library)`: la app necesita `gradle/libs.versions.toml` con `android-library` y declarar `alias(libs.plugins.android.library) apply false` en el `build.gradle(.kts)` raíz. Además, excluir en la app `META-INF/DEPENDENCIES` y `META-INF/INDEX.LIST` (`packaging { resources { excludes += ... } }`).
- Las versiones de AGP de la app y de las librerías deben ser compatibles: la librería toma el AGP de la app (plugins con `apply false` en la raíz).
- Los tests de las librerías no siempre compilan desde la app: correr `:app:testDebugUnitTest`, no `test` en todos los módulos.
- **custom-ads** está en Java: no cambia la regla de lenguaje de la app.
- La ruta absoluta solo funciona en esta PC. En CI u otra PC: clonar las librerías en las mismas rutas o pasar a JitPack (última etiqueta: `git tag | sort -V`). Anotarlo en el README del proyecto.
- Con R8 (release minificado): las entidades de DAL se mapean por reflexión; agregar `-keep` de su paquete en `proguard-rules.pro` si la librería no lo trae en `consumer-rules.pro`.

## Extender una librería (p. ej. algo nuevo en SQLite)

Cuando una app necesita algo que la librería no tiene, **se agrega en la librería**, no un parche en la app:

1. Leer el código y los usos actuales en las otras apps (`grep` en `D:/Projects/Android/*/`) antes de cambiar nada.
2. **Compatibilidad hacia atrás**: métodos u opciones nuevas con valores por defecto que mantienen el comportamiento actual; nunca cambiar firmas, nombres de columnas, formato de fechas ni el orden de migraciones existentes. Lo nuevo es opt-in.
3. Un test en la librería que cubra lo nuevo y uno que pruebe que lo viejo sigue igual.
4. Compilar al menos otra app que use la librería (p. ej. un `assembleDebug` de la más grande) para comprobar que nada se rompió.
5. Commit en el repo de la librería **solo con permiso** del usuario, en su propia rama, con un mensaje que diga qué app lo necesitó. Si la librería se publica en JitPack, la etiqueta nueva también la decide el usuario.
