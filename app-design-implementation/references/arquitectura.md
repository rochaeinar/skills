# Arquitectura, buenas prácticas y calidad de código

Guía para Android (Kotlin + Compose). En un proyecto solo Java se aplican los mismos principios en Java (ViewModel + `LiveData`/estado inmutable, interfaces para los puertos, sin lógica en las Activities) con su sistema de UI existente. Para otro stack, aplicar los mismos principios con sus herramientas. Si el proyecto ya tiene una arquitectura sana, se respeta; si no, se propone el cambio en la fase 2.

## Capas (Clean Architecture pragmática, guía oficial de Android)

```
ui/            Pantallas Compose + ViewModel por pantalla (estado + eventos)
domain/        Modelos de negocio, casos de uso con lógica real, puertos (interfaces)
data/          Repositorios, fuentes de datos (Room, DataStore, red), mapeos
platform/      Adaptadores de hardware y sistema (Bluetooth, notificaciones, permisos, reloj)
di/            Composición: qué implementación va con cada puerto (real o doble)
testing/ (debug) Dobles reales, escenarios, panel de pruebas
```

- La dependencia apunta hacia adentro: `ui → domain ← data/platform`. El dominio no conoce Android.
- **Casos de uso solo si tienen lógica** (validar, combinar repositorios, reglas). Un caso de uso que solo reenvía una llamada es ruido: el ViewModel llama al repositorio.
- **Un módulo Gradle** basta para una app chica o mediana; separar en módulos (`:core:designsystem`, `:feature:x`) solo si el proyecto es grande o ya lo está. Se decide en la fase 2.

## UI: flujo de datos unidireccional (UDF / MVI liviano)

- Cada pantalla: `data class XUiState` inmutable, un `sealed interface XEvent` (acciones del usuario) y efectos de una sola vez (navegar, snackbar) por `Channel`/`SharedFlow`.
- El ViewModel expone `StateFlow<XUiState>` (`stateIn(WhileSubscribed(5_000))`) y una función `onEvent(event)`.
- La pantalla se divide en `XRoute` (obtiene el ViewModel, recoge el estado con `collectAsStateWithLifecycle`) y `XScreen(state, onEvent)` sin estado: así se previsualiza y se prueba sin ViewModel.
- Composables chicos, sin lógica de negocio; `remember`/`derivedStateOf` solo para estado de UI; claves estables en listas (`key = { it.id }`).
- Estados del diseño = ramas explícitas del estado (`Loading`, `Empty`, `Content`, `Error`, `NoPermission`…), no booleanos sueltos que pueden contradecirse.

## SOLID aplicado

- **S** — una razón para cambiar: el ViewModel coordina, el caso de uso decide, el repositorio guarda, el adaptador habla con el hardware. Si una clase pasa de ~300 líneas o mezcla dos de esos roles, se divide.
- **O** — abierto a extensión: distribuciones de teclado, tipos de macro, proveedores, se agregan como implementaciones/entradas nuevas (estrategia, tabla), no con otro `when` gigante.
- **L** — los dobles reales y los adaptadores reales cumplen el mismo contrato (mismo comportamiento observable, mismos errores): lo garantizan tests de contrato compartidos.
- **I** — puertos chicos y por uso (`HidConnection`, `HidReports`, `PairingGateway`) en vez de una interfaz enorme.
- **D** — la app depende de puertos; la DI decide la implementación. Nada de `object` globales con estado ni `context.applicationContext as App` para sacar dependencias.

## Patrones que suelen ayudar (usarlos solo si resuelven algo)

| Patrón | Para qué |
|---|---|
| Puertos y adaptadores (hexagonal) | Todo hardware/sistema externo detrás de una interfaz: real, doble real y fake de test |
| Repositorio | Una fuente de verdad por tipo de dato; la UI no sabe si viene de Room o de memoria |
| Máquina de estados | Conexión, emparejamiento, grabación, reproducción: estados y transiciones explícitos y testeables |
| Estrategia | Distribuciones de teclado, modos de repetición, formatos |
| Comando | Acciones grabables/reproducibles (macros), deshacer |
| Observador (Flow) | Estado del sistema que cambia (Bluetooth, conexión, progreso) |
| Fábrica / builder | Construir reportes, notificaciones, intents de forma legible |
| Decorador | Registro/medición alrededor de un puerto sin tocarlo |

## Clean code

- Nombres que dicen qué y por qué (`reconnectDelay`, no `d2`); sin abreviaturas raras; un idioma (inglés) en el código.
- Funciones cortas, un nivel de abstracción por función, sin parámetros booleanos que cambian el comportamiento (dos funciones).
- Sin números mágicos: constantes con nombre y unidad (`VISIBILITY_SECONDS = 300`).
- Errores explícitos: `Result`/tipos sellados en el dominio; nada de `catch (e: Exception) {}` vacío ni `Log` como manejo de error; cada error del diseño tiene su estado de UI.
- Corrutinas: `viewModelScope`, dispatchers inyectados, nada de `Thread.sleep` ni `GlobalScope`; cancelación respetada.
- Sin código muerto, sin comentarios que repiten el código; comentarios solo para el **porqué** (una regla de la plataforma, un dato del protocolo con su referencia).
- Formato y estilo automáticos (ktlint o el formateador del proyecto).

## Mantenible por personas (sin IA)

- Estructura predecible: una carpeta por pantalla (`ui/home/HomeRoute.kt`, `HomeScreen.kt`, `HomeViewModel.kt`, `HomeUiState.kt`), mismo patrón en todas.
- Un `README.md` del proyecto (o `docs/arquitectura.md`) con: capas, cómo agregar una pantalla, cómo correr tests y Maestro, cómo usar los dobles reales y el panel de pruebas, y decisiones importantes (ADR cortos).
- KDoc solo en puertos y en lógica no obvia (protocolos, reglas de negocio).
- Nada generado sin entender: el código tiene que poder explicarse línea por línea.
- Dependencias con catálogo de versiones (`libs.versions.toml`), pocas y conocidas.

## Tema y sistema de diseño

- Tokens del diseño (`design/plan.md`, tablero DesignSystem) → `Color.kt` (esquemas claro y oscuro, roles de Material 3 + colores extra como `ExtendedColors` por `CompositionLocal`), `Type.kt`, `Shape.kt`, espaciados (`Dimens`), duraciones de movimiento.
- Componentes del diseño como composables reutilizables en `ui/designsystem/` con sus estados (normal, presionado, foco, deshabilitado, error).
- Nunca colores, medidas ni fuentes sueltas en una pantalla. Sin color dinámico salvo que el diseño lo pida.

## Adaptativo

- `WindowSizeClass` (compacto / medio / expandido) y orientación decide el layout, exactamente como en los tableros adaptativos: lista-detalle, riel de navegación, dos paneles; nunca el layout del teléfono estirado.
- Probar la rotación sin perder estado (`SavedStateHandle`, `rememberSaveable`) y la muerte del proceso.
- Plegables y ventanas múltiples: que no se rompa al cambiar el tamaño.

## Idiomas y accesibilidad

- Todos los textos en `strings.xml` (en inglés durante la implementación; las traducciones al final, `idiomas.md`), plurales con `pluralStringResource`, formatos con marcadores, nada concatenado.
- RTL: `start/end`, íconos direccionales espejados solo donde el diseño lo indica.
- Fuente al 200 %: nada cortado; alturas mínimas, no fijas, en textos.
- `contentDescription` y semántica (roles, estados, `liveRegion`) como en las anotaciones del diseño; objetivos táctiles ≥ 48 dp; contraste del diseño.

## Datos

- Base de datos con **data-access** (DAL), logs con **RestLog4Android** y sincronización con Drive con **synchronizer**: ver `librerias-propias.md` (entidades de DAL solo en la capa de datos, mapeadas a modelos de dominio; migraciones con `UpgradeListener` probadas). Room solo si el proyecto ya lo usa, con `MigrationTestHelper` y nunca `fallbackToDestructiveMigration` en producción si hay datos de usuarios.
- Preferencias en DataStore. Datos sensibles nunca en logs (`librerias-propias.md` §Reglas de seguridad de los logs) ni fuera del almacenamiento interno (`seguridad.md`).

## Robustez de plataforma

- Permisos con explicación y salida (como en el diseño), `shouldShowRequestPermissionRationale`, "no volver a preguntar".
- Servicios en primer plano con el tipo correcto y su notificación; trabajo en segundo plano con WorkManager si corresponde.
- Versiones de API: comprobar cada API contra `minSdk` y la versión vigente de Google Play.

## Extras recomendados (proponerlos en la fase 2)

- Análisis estático: Android Lint con `warningsAsErrors` en lo crítico, detekt, ktlint.
- Debug: StrictMode (disco/red en hilo principal), LeakCanary.
- Tests de captura de pantalla (Roborazzi o Paparazzi) de cada estado claro/oscuro/teléfono/tablet: comparan con el diseño y evitan regresiones visuales.
- Baseline Profiles y Macrobenchmark para el arranque y las listas.
- CI (GitHub Actions / Bitbucket Pipelines): compilar, lint, unit tests, build release en cada push.
- Reporte de crashes (Firebase Crashlytics u otro) si el usuario lo acepta (implica política de privacidad).
- Commits pequeños por pantalla con mensajes claros; ADR para decisiones de arquitectura.
- Ya obligatorios (no son extras): monkey testing (`scripts/monkey.py`) y seguridad OWASP MASVS (`seguridad.md`) en la fase 6.
