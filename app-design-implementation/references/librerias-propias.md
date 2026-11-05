# Librerías propias: base de datos, logs y sincronización con Drive

Las apps del usuario usan sus propias librerías. Son la opción por defecto para persistencia, logs y sincronización; Room, Timber o un sync propio solo si el proyecto ya los usa o el usuario lo decide en la fase 2. Antes de usarlas, leer su README/CLAUDE.md y su API real (pueden haber cambiado desde que se escribió esta guía).

| Necesidad | Librería | Ruta local | Paquete |
|---|---|---|---|
| Base de datos (ORM SQLite) | data-access (DAL) | `D:\Projects\Android\data-access\DataAccessLayer\dal` | `com.erc.dal` |
| Logs | RestLog4Android | `D:\Projects\Android\RestLog4Android\RestLog` | `com.erc.log` |
| Sincronización / respaldo en Google Drive (solo si la app sincroniza con Drive) | synchronizer | `D:\Projects\Android\synchronizer\app` | `com.erasoft.synchronizer` |

## Cómo se incluyen

Como módulos de código fuente en `settings.gradle(.kts)` (así lo hacen `forever-note` y `tracker`), no por JitPack, para depurar y corregir en la propia librería:

```kotlin
include(":dal")
project(":dal").projectDir = file("D:/Projects/Android/data-access/DataAccessLayer/dal")
include(":restlog")
project(":restlog").projectDir = file("D:/Projects/Android/RestLog4Android/RestLog")
include(":synchronizer")                     // solo con sync en Drive
project(":synchronizer").projectDir = file("D:/Projects/Android/synchronizer/app")
```

```kotlin
implementation(project(":dal"))
implementation(project(":restlog"))          // RestLog desde fuente también necesita ':dal'
implementation(project(":synchronizer"))     // usa ':dal' como compileOnly: la app lo provee
```

- Una ruta absoluta de Windows rompe la compilación en CI y en otras PCs: preguntar en la fase 2 si se mantiene la ruta local, se usa JitPack (`com.github.rochaeinar:data-access` / `RestLog4Android`, con la última etiqueta: `git tag | sort -V`) o un submódulo de git. Documentarlo en el README del proyecto.
- Un cambio dentro de una librería es un cambio en otro repositorio: anotarlo en `decisiones.md`, mantener la compatibilidad con las otras apps que la usan y no hacer commit ni push en ese repo sin permiso.

## data-access (DAL)

- Entidades que extienden `Entity`, con `@Table`, `@Field` y `@PrimaryKey`. En Kotlin, con `@field:` (ver `forever-note/.../models/Note.kt`):
  ```kotlin
  @Table(name = "devices")
  class DeviceRow : Entity() {
      @field:PrimaryKey @field:Field(name = "id") var id: Long = 0
      @field:Field(name = "name") var name: String = ""
  }
  ```
- `DB` / `DBs.getInstance().getDB(config)` (una sola instancia por archivo), `DBConfig(context, nombre, versión, ruta)`, `setPackageFilter` para que el arranque sea rápido, y un `UpgradeListener` con migraciones explícitas por versión. `Options`, `Group`, `Aggregation` y `Function` para las consultas.
- Todo falla con `DALException` (unchecked): se captura en el **adaptador**, que lo traduce a un error del dominio. Nunca llega a la UI ni se traga.
- **Arquitectura**: las entidades de DAL son el modelo de **datos**, no del dominio. El repositorio (adaptador) mapea `DeviceRow` ↔ `Device` (modelo de dominio inmutable); el dominio y la UI no importan `com.erc.dal`. Las llamadas van en `Dispatchers.IO` (DAL es síncrono), expuestas como `suspend` o `Flow`.
- Tests: el mapeo y la lógica del repositorio con un doble del puerto en JVM. Las migraciones (`UpgradeListener`) con un test instrumentado: crear la base en la versión vieja, migrar, verificar los datos.
- Reflexión: con R8 activado, revisar `consumer-rules.pro` de la librería y agregar `-keep` de las entidades si hace falta. El humo de Maestro sobre el release lo detecta.

## RestLog4Android (logs)

- API: `Log.e/w/i/d/v(tag, mensaje[, excepción])` de `com.erc.log`, configurado por `assets/rest-log.json` (appenders `logcat`, `file`, `database`, `rest`, `overlay`, `console`; `level`, `filters`, `maxFileSizeMb`, `deleteAfter`).
- **Una sola fachada en la app** (`AppLogger`, interfaz en el dominio o en `core`, implementada con RestLog), así el código no depende de la librería y en los tests se usa un doble que guarda los mensajes.
- **Configuración por tipo de build**: `src/debug/assets/rest-log.json` (nivel `debug`, `logcat` + `file` + `overlay`) y `src/release/assets/rest-log.json` (nivel `warn`, solo `file` interno o `logcat`; sin `rest`, sin `overlay`).

### Reglas de seguridad de los logs (obligatorias)
1. **Nada sensible, nunca, en ningún nivel**: contraseñas, tokens, claves, correos, nombres, teléfonos, direcciones MAC o de Bluetooth completas, ubicación, contenido escrito por el usuario (lo tecleado en un teclado remoto, notas, mensajes), cuerpos de solicitudes HTTP. Si hace falta identificar algo, enmascararlo (`AA:BB:**:**:**:FF`, los últimos 4 caracteres, un hash).
2. Una función `redact()` en la fachada para los casos conocidos, **con unit test**: es lógica que protege algo.
3. Los mensajes describen eventos y estados ("conexión HID rechazada, estado=3"), no datos.
4. **Release**: nivel `warn` o mayor, sin `overlay` (la librería ya lo ignora si la app no es depurable, salvo `force`), sin `rest`. Si se quiere un `rest` en producción: solo HTTPS, con consentimiento, declarado en Data safety y en la política de privacidad.
5. **Almacenamiento**: el appender `file` escribe en `getExternalFilesDir` y la exportación del panel y `MoveLogsJobIntentService` en **Descargas (pública)**. En release, sin exportación a Descargas; los archivos rotan (`deleteAfter`, `maxFileSizeMb`).
6. **Manifiesto**: la librería agrega `INTERNET`, `RECEIVE_BOOT_COMPLETED`, `WAKE_LOCK`, `ACCESS_NETWORK_STATE` y receptores/servicios exportados. Lo que la app no use se quita con `tools:node="remove"` en el manifiesto de la app; si quedan, se justifican en Play.
7. El QA lo verifica: `adb logcat` durante toda la pasada de Maestro y búsqueda de los patrones sensibles (`references/seguridad.md`).

## synchronizer (Google Drive)

Solo si la app sincroniza o respalda datos en Drive (es pregunta de la fase 2 si el diseño muestra sincronización, respaldo o "varios dispositivos").

- Las entidades sincronizables implementan `Synchronizable` (`itemStatus`, `lastUpdated`, `syncStatus`), además de `Entity` de DAL.
- Una `SyncConfiguration` por base: `getDbConfig`, campos de estado, `getItemsClass`, `getRawFileName`, carpeta en Drive (`getRootFolderName`: si ya hay datos en producción, conservar el nombre), `isNewer` / `merge` para los conflictos, `isBackupEnabled`. Ejemplo real: `forever-note/.../sync/NoteSyncConfiguration.kt`.
- `DriveInitializer` (cuenta y autorización) en la Activity; `Synchronizer(context, activity, config).synchronize()` en un `CoroutineWorker` de WorkManager (restricción de red), con `SyncProgressListener` hacia el estado de la UI. `EncryptionConfig.configure(true, secreto)` si los datos lo merecen (el secreto no va fijo en el código).
- Detrás de un puerto (`SyncGateway`) con su **doble real** (`FakeDrive` en memoria que reproduce la API: carpeta raíz, archivo de la base, conflictos, sin conexión, cuenta revocada, cuota llena) para que Maestro pruebe los estados de sincronización sin cuenta de Google.
- Unit tests de la configuración que tiene lógica (`isNewer`, `merge`): son exactamente el tipo de lógica que protege datos.
- Play: Drive implica cuenta de Google, `INTERNET`, Data safety (datos guardados en la cuenta del usuario) y verificación del cliente OAuth si se usan alcances sensibles.
