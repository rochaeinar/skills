# Revisión profunda del código

El inventario (`scripts/inventario.py`) es solo el mapa. La revisión es leer cada archivo completo y entenderlo.

## Orden de lectura
1. **Configuración:** `AndroidManifest.xml` (actividades, permisos, servicios, receivers, intent-filters, `exported`), `build.gradle(.kts)` (minSdk, targetSdk, dependencias: dicen qué puede hacer la app: Room, Retrofit, WorkManager, Billing, AdMob, CameraX, ML Kit…), `settings.gradle` (módulos).
2. **Modelo de datos:** entidades (`@Entity`, data classes, tablas SQL), DAO y sus consultas, DataStore/SharedPreferences (cada clave), APIs de red (`@GET/@POST`, modelos de respuesta), archivos y assets. → Esto define **qué datos existen**: la base para juzgar si una mejora es posible.
3. **Lógica:** repositorios, casos de uso, servicios, workers, ViewModels (cada `StateFlow`/`LiveData` es algo que la pantalla muestra; cada función pública es una acción del usuario).
4. **Interfaz:** cada Activity, Fragment, `@Composable`, layout XML, menú, navegación; diálogos, sheets y popups; `strings.xml`, `colors.xml`, `themes.xml`, `dimens.xml`, drawables e íconos.
5. **Pruebas y docs:** tests (describen comportamiento esperado), README, CHANGELOG, notas de versión, flujos de Maestro.

## Ficha de análisis por pantalla (en `analisis.md`)
- **Identidad:** nombre, archivos (`archivo:línea`), ruta de navegación.
- **Objetivo:** qué tarea del usuario resuelve, en una frase.
- **Entradas y salidas:** desde dónde se llega (y con qué argumentos), adónde puede ir, qué devuelve (resultado, `setResult`, `savedStateHandle`).
- **Datos:** cada dato visible → su fuente (ViewModel → repositorio → tabla/campo, preferencia, red, sensor, sistema). Formato (fecha, número, unidad).
- **Acciones:** cada elemento interactivo (botón, ítem, ícono, gesto, tecla física, atajo) → qué método llama → qué cambia.
- **Estados:** carga, vacío, error (¿cuáles errores puede haber? excepciones capturadas, códigos de red), sin conexión, sin permiso, deshabilitado, primer uso, contenido, contenido extremo. Señalar los que el código **no** maneja (deuda de UX).
- **Comportamientos:** diálogos (`AlertDialog`, `Dialog`, `DialogFragment`), bottom sheets, menús (`DropdownMenu`, `PopupMenu`, `menu/*.xml`), snackbars, toasts, selectores de fecha/hora/archivo, permisos en tiempo de ejecución, deslizables (`SwipeToDismiss`), arrastrar, pull-to-refresh, pestañas, paginación, animaciones, vibración, notificaciones, overlays, pantalla completa, orientación forzada, teclado (IME actions).
- **Validaciones y reglas:** límites, formatos, campos obligatorios, mensajes.
- **Textos:** las claves de `strings.xml` que usa; los textos fijos en el código (deuda).
- **Plataforma:** permisos, comportamiento al rotar, al volver del segundo plano, con fuente grande, en tablet.

## Equivalencias en otras plataformas
| Concepto | Flutter | iOS (SwiftUI/UIKit) | Web/React Native |
|---|---|---|---|
| Pantalla | `StatelessWidget`/`StatefulWidget` en rutas (`GoRouter`, `Navigator`) | `struct …: View`, `UIViewController` | componentes de página, `react-navigation` |
| Diálogo / sheet | `showDialog`, `showModalBottomSheet` | `.alert`, `.sheet`, `.confirmationDialog` | `Modal`, `Dialog` |
| Mensaje | `ScaffoldMessenger.showSnackBar` | banner propio, `.alert` | toast |
| Datos | `sqflite`, `drift`, `hive`, `shared_preferences` | Core Data, SwiftData, `UserDefaults` | `AsyncStorage`, IndexedDB, API |
| Textos | `.arb` | `Localizable.strings`/`.xcstrings` | `i18n/*.json` |

## Juzgar si una mejora es posible
Una mejora entra si y solo si se puede contestar con evidencia:
1. ¿Qué dato necesita? → ¿Se guarda ya (tabla/campo/preferencia) o se puede **calcular** con lo guardado?
2. ¿Qué capacidad necesita? → ¿La plataforma la da con los permisos actuales o con uno razonable?
3. ¿Necesita servidor, cuenta, IA o un servicio pago que la app no tiene? → descartada (o pregunta, si el usuario mencionó que lo quiere agregar).
4. ¿Cuánto cuesta implementarla (S/M/L) y qué tanto ayuda al usuario?
Si un dato no se guarda pero guardarlo es trivial (p. ej. la fecha de último uso), proponerlo como mejora M con esa aclaración.
