# Dispositivos: teléfono conectado, emuladores existentes, reintentos

## Qué se usa

- `python scripts/devices.py` lista los dispositivos en estado `device` (serial, modelo, Android, tamaño de pantalla, densidad, si es emulador y si es tablet) y los emuladores (AVD) ya creados.
- **Teléfono físico conectado**: el principal para probar.
- **Emulador**: solo si ya está creado y configurado. Se puede iniciar uno existente (`emulator -avd <nombre> -no-snapshot-save` en segundo plano) si el usuario lo autorizó en la fase 2. **Nunca se crea un AVD nuevo** ni se descargan imágenes del sistema.
- Varios dispositivos a la vez: Maestro en paralelo (`maestro.md`). Un tablet o emulador de tablet cubre los flujos adaptativos.

## Cuándo probar en dispositivo

- Al tener los cimientos (tema, navegación) y la primera pantalla: humo para detectar problemas de entorno temprano.
- Al terminar el flujo principal y cada flujo grande.
- Siempre que se toque algo que depende del hardware real.
- Al final, todo (fase 6), incluido el release.

Cada vez: `./gradlew installDebug` (o el release en la fase 6), flujos Maestro de lo hecho, `adb logcat -b crash` y búsqueda de `FATAL EXCEPTION`, `ANR`, `StrictMode` en el log del proceso.

## Si el dispositivo se desconecta

1. **No detenerse.** Anotar en `impl/progreso.md`: hora, qué pruebas quedaron pendientes.
2. Lanzar en segundo plano (herramienta Bash con `run_in_background: true`):
   `python scripts/devices.py --wait --interval 600`
   Revisa cada 10 minutos (600 s) y termina en cuanto hay un dispositivo; al terminar, la sesión recibe el aviso y se corren las pruebas pendientes. No hace falta consultarlo mientras tanto.
3. **Seguir implementando todo** lo que falta. Las pruebas pendientes se acumulan.
4. Si el dispositivo no vuelve, el usuario lo resolverá cuando esté disponible: se termina el código, los unit tests y los flujos Maestro (escritos y validados en sintaxis con `maestro check-syntax` si la versión lo tiene), y `progreso.md` deja la lista exacta de lo que falta correr en dispositivo.
5. Nunca reiniciar el servidor de adb del usuario ni tocar la configuración del teléfono más allá de instalar/desinstalar la app (si se autorizó).

## Requisitos del teléfono (para el usuario, en la fase 2)

Depuración USB activada, la PC autorizada, pantalla sin bloqueo (o con "mantener la pantalla encendida mientras carga" en opciones de desarrollador), animaciones reducidas opcionales para Maestro.
