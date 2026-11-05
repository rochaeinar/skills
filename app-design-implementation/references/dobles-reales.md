# Dobles reales ("real devices mock")

Un **doble real** es un emulador, escrito en el código de la app, de algo externo que la app no controla: otro equipo, un periférico, el sistema operativo, un servidor, la base de datos con datos reales, el reloj. Se comporta como el real (estados, tiempos, errores) y se puede controlar desde las pruebas.

Son muy importantes: con ellos **Maestro prueba el 100 % de la funcionalidad aunque no haya hardware ni otro equipo**, en cualquier dispositivo y en paralelo. El hardware real se prueba además, cuando esté disponible, pero nunca es un requisito para avanzar.

## 1. Investigar la interfaz real (fase 1)

Para cada interfaz externa, antes de escribir el doble:
- Documentación oficial (Android Developers, la especificación del protocolo, la del fabricante) y el código actual que la usa (`archivo:línea`).
- Estados posibles y transiciones, qué eventos/callbacks llegan y en qué orden, tiempos típicos y límites (time-outs, duraciones), errores reales y cómo se manifiestan, datos que viajan (formato exacto).
- Comportamiento del otro lado (qué hace el equipo remoto con lo que recibe, qué guarda en caché, qué ve el usuario allí).
- Anotarlo en `impl/analisis.md` §Interfaces externas con las fuentes. El doble se basa en esto, no en suposiciones.

## 2. Diseño: puerto + adaptador real + doble real

```kotlin
// domain: el puerto, lo único que conoce la app
interface HidHost {
    val state: StateFlow<HostState>           // Unregistered, Ready, Pairing, Connecting, Connected, ...
    suspend fun connect(address: String): Result<Unit>
    fun send(report: HidReport)
}

// platform: adaptador real (BluetoothHidDevice)
class BluetoothHidHost(...) : HidHost

// testing (solo debug): doble real
class EmulatedHidHost(private val pc: VirtualComputer, private val clock: Clock) : HidHost
```

- El doble **simula el otro lado**, no solo responde "ok": p. ej. una `VirtualComputer` que empareja con código, recuerda el emparejamiento (y lo "olvida"), guarda en caché el descriptor, decodifica los reportes HID (teclas → texto según la distribución, movimiento → posición del puntero, clicks, scroll) y expone lo recibido.
- Tiempos realistas pero configurables (y acelerables en tests).
- Inyección de fallos: desconexión, sueño del equipo, emparejamiento rechazado o vencido, emparejamiento viejo sin descriptor, error de controlador, fuera de alcance, Bluetooth apagado, permiso denegado.
- **Tests de contrato**: un mismo conjunto de tests abstractos (`HidHostContract`) corre contra el doble y, en instrumentados con hardware, contra el real. Garantiza que el doble no miente (Liskov).

Ejemplos típicos:

| Externo | Doble real |
|---|---|
| PC/TV por Bluetooth HID | Computadora virtual: emparejamiento, caché, decodificación de reportes, pantalla virtual con texto y puntero |
| El teléfono / el sistema | Estado de Bluetooth, permisos, visibilidad, batería, red, notificaciones como fuentes controlables |
| Base de datos | Escenarios sembrados: vacía, típica, muchos datos, textos largos, datos corruptos o de una versión vieja (para migraciones) |
| Servidor/API | Servidor en memoria o MockWebServer con respuestas reales grabadas, errores 4xx/5xx, lentitud, sin conexión |
| Reloj | `Clock` inyectado y avanzable (programaciones, time-outs, "hace 2 h") |
| Compras/anuncios | Implementaciones de prueba de la librería oficial o un doble con los estados reales |

## 3. Escenarios y control desde Maestro

- **Solo en debug** (`src/debug/` o un sabor `mock`): el doble, los escenarios y un receptor de control. El release no los incluye; comprobarlo en la fase 6.
- Un enlace profundo de prueba que Maestro abre con `openLink`, p. ej. `myapp-test://scenario?name=connected_with_macros&host=windows&fail=pairing_timeout`. Carga el escenario (datos + estado de los dobles) y abre la pantalla pedida.
- Un **panel de pruebas** (pantalla debug, accesible por el enlace o una notificación debug) que muestra lo que recibió el equipo virtual (texto escrito, posición del puntero, clicks) y permite disparar fallos. Maestro comprueba con `assertVisible` sobre el panel o sobre un overlay de debug.
- Escenarios con nombre y documentados en `README` (qué datos, qué estado, qué falla), reutilizados por tests de unidad, previews y Maestro.
- Elegir la implementación por DI: `debug` + escenario → doble; `debug` sin escenario → real (para probar hardware); `release` → siempre real.

## 4. Lo que no hace un doble

- No reemplaza la prueba con hardware real cuando existe: los flujos con etiqueta `real` se corren cuando hay un dispositivo y el equipo externo disponible, y el resultado va al informe de QA.
- No agrega funciones que la app real no tiene ni oculta errores del adaptador real.
