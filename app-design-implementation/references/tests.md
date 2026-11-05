# Tests: inteligentes, no estrictos

La meta **no** es el 100 % de cobertura. Cada test tiene que proteger algo que puede romperse y que costaría caro: si nunca fallaría, o solo repite la implementación, no se escribe.

## Qué merece un unit test (sí)

- **Lógica de negocio y reglas**: validaciones, cálculos, programaciones (intervalos, repeticiones, "próxima ejecución"), límites.
- **Máquinas de estado**: conexión, emparejamiento, grabación, reproducción; cada transición, incluidas las de error y la recuperación.
- **Protocolos y formatos**: construcción y decodificación de mensajes/reportes (bytes exactos según la especificación), tablas de conversión (p. ej. carácter → código HID por distribución), serialización de lo que se guarda.
- **ViewModels con decisiones**: que un evento produzca el estado y el efecto correctos (con dobles de los puertos y `kotlinx-coroutines-test`, `Turbine` para flows).
- **Migraciones de base de datos** (`MigrationTestHelper`) y consultas con lógica (filtros, orden, búsqueda).
- **Bugs corregidos**: cada bug de lógica encontrado en QA deja su test de regresión.
- **Tests de contrato** de los dobles reales (ver `dobles-reales.md`).

## Qué no (no)

- Getters, `data class`, mapeos triviales campo a campo, constantes.
- Composables solo para ver que "existen"; la UI se cubre con el humo y Maestro.
- Mocks de todo para verificar que se llamó un método (`verify(x).foo()`) sin comprobar un resultado.
- Tests que copian la implementación (mismo cálculo en el test) o que dependen del orden o del tiempo real.

Antes de escribir un test: "¿qué cambio razonable en el código haría fallar este test, y ese fallo sería un bug real?" Si no hay respuesta, no se escribe.

## Estilo

- Nombre que describe el comportamiento: `` `reconnects after disconnect when auto-reconnect is on` ``.
- Arrange / Act / Assert, un comportamiento por test, datos mínimos y legibles (builders de prueba).
- Dobles (fakes en memoria) mejor que mocks; los mismos fakes que usa el doble real si sirve.
- Reloj y dispatchers inyectados: nada de `Thread.sleep`.
- Rápidos: los unit tests en JVM (`test/`); instrumentados (`androidTest/`) solo para lo que necesita Android (Room, migraciones, humo).

## Humo (happy path) por pantalla

Para evitar crashes obvios, cada pantalla tiene un test de humo muy básico:
- Instrumentado de Compose (`createAndroidComposeRule`) o Robolectric: abrir la pantalla con un escenario típico (de los dobles reales), comprobar que aparece su elemento principal y ejecutar su acción principal sin crash.
- Uno por pantalla, no por variante. Las variantes se cubren con previews/capturas y Maestro.
- Si el proyecto tiene tests de captura (Roborazzi/Paparazzi), el humo puede ser la captura de cada estado.

## Comandos

- `./gradlew testDebugUnitTest` (unit), `./gradlew connectedDebugAndroidTest` (instrumentados, con dispositivo), `./gradlew lint`.
- Todo en verde antes de marcar una pantalla como hecha.
