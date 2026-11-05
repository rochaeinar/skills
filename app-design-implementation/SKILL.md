---
name: app-design-implementation
description: Implementa al 100 % el diseño de una app móvil (Android por defecto) hecho en Claude Design - cada pantalla, estado y comportamiento, en teléfono y tablet, vertical y horizontal, claro y oscuro, en todos los idiomas - con arquitectura limpia (SOLID, patrones, código mantenible por personas sin IA), unit tests solo donde protegen lógica real, un happy path de humo por pantalla, automatización Maestro de todas las pantallas que corre en paralelo en varios dispositivos, "dobles reales" (emuladores en código de las interfaces externas, p. ej. una PC Bluetooth HID, el teléfono, la base de datos) para que nada bloquee las pruebas, y un cierre con rol de QA hasta dejarla lista para Google Play. Todo lo dudoso o no factible se pregunta al principio; después trabaja solo durante horas (toda la noche), probando en el teléfono conectado o en un emulador ya configurado y reintentando la conexión cada 10 minutos sin dejar de programar. Úsalo cuando pidan "implementar el diseño", "programar las pantallas del diseño", "pasar el diseño de Claude Design a código", "implementar el rediseño", "dejar la app lista para producción según el diseño" o "implementa todo lo de design/".
---

# Implementación de diseños de Claude Design

El objetivo es una app **100 % funcional, usable y lista para subir a Google Play**, idéntica al diseño. No es "que compile" ni "que funcione en el caso feliz": se implementa todo, se prueba como un QA exigente y se entrega código que cualquier persona puede mantener sin IA.

**Reglas de oro**
1. **Nada se omite.** Cada pantalla, variante, estado, diálogo, hoja, menú, snackbar, deslizable, animación, texto y caso borde del diseño se implementa. Si algo no es factible, se pregunta en la fase 2, nunca se deja a medias ni se reemplaza en silencio.
2. **Todo se resuelve al principio.** Después de la fase 2 no se vuelve a preguntar: se trabaja de forma autónoma (horas, toda la noche) y las dudas menores se deciden y se anotan.
3. **Un dispositivo desconectado no detiene el trabajo.** Solo detiene las pruebas en dispositivo real; el código sigue.
4. **Las dependencias externas nunca bloquean las pruebas.** Cada interfaz externa (hardware, otro equipo, red, base de datos, tiempo, permisos) tiene un doble real en código.
5. **Calidad de producción.** Arquitectura clara, SOLID, patrones donde ayudan, clean code; nada de código "de IA" difícil de seguir.

Referencias (leer cada una en la fase donde se usa):
- `references/arquitectura.md`: arquitectura móvil, capas, SOLID, patrones, clean code, Compose, adaptativo, temas, idiomas, errores. **Fase 3 y toda la implementación.**
- `references/dobles-reales.md`: cómo investigar una interfaz real y construir su emulador en código (puertos y adaptadores, escenarios, panel de pruebas). **Fase 1-3.**
- `references/tests.md`: qué merece un unit test y qué no, el happy path de humo por pantalla. **Fase 4-5.**
- `references/maestro.md`: estructura, ids, flujos independientes, paralelo en varios dispositivos, qué automatizar. **Fase 5.**
- `references/dispositivos.md`: teléfono conectado, emuladores existentes, reintento cada 10 minutos. **Fase 0 y 4-6.**
- `references/qa.md`: el rol de QA, la lista de producción y Google Play, formato de bugs. **Fase 6.**
- `templates/`: `preguntas.md`, `plan.md`, `progreso.md`, `qa-informe.md`.
- `scripts/`: `cobertura_diseno.py` (matriz de pantallas y variantes desde el lienzo), `devices.py` (dispositivos y espera con reintento), `maestro_paralelo.py` (Maestro repartido entre todos los dispositivos).

## Carpeta de trabajo

Todo el estado queda en `impl/` en la raíz del proyecto (con él se retoma un trabajo interrumpido, también tras resumir el contexto):

| Archivo | Fase | Contenido |
|---|---|---|
| `impl/cobertura.md` | 1 | Matriz: cada pantalla y variante del diseño → archivo de código, test, flujo Maestro, QA. Generada con `cobertura_diseno.py` y mantenida a mano. |
| `impl/analisis.md` | 1 | Diseño leído, código actual, brechas, interfaces externas y su doble real, riesgos. |
| `impl/preguntas.md` | 2 | Todo lo no factible, ambiguo o contradictorio, con opciones y recomendación. |
| `impl/decisiones.md` | 2-6 | Cada decisión (del usuario o propia) y su motivo. |
| `impl/plan.md` | 3 | Arquitectura, módulos, orden de implementación, tests y flujos previstos. |
| `impl/progreso.md` | 4-6 | Lo hecho, lo que falta, estado de los dispositivos, siguiente paso. Se actualiza después de cada pantalla. |
| `impl/qa-informe.md` | 6 | Resultado del QA, bugs encontrados y corregidos, veredicto de producción. |

Si `impl/` ya existe: leer `progreso.md` y seguir desde ahí sin repetir fases cerradas.

## Flujo de trabajo

### 0. Entrada y entorno
- **El diseño**: por defecto `design/` del proyecto (lo que deja el skill `app-screen-design`: `design/canvas/*.dc.html` + `canvas.json`, `pantallas/*.md`, `plan.md`, `decisiones.md`, `entrega.md`, `strings/`). Si pasan un enlace de Claude Design, leerlo con la herramienta Artifact (`read`, archivos `project/canvas.json` y cada `project/*.dc.html`) y guardar una copia en `design/canvas/`. Si no hay diseño, este skill no aplica: sugerir `app-screen-design`.
- **Plataforma**: Android (Kotlin + Jetpack Compose + Material 3) salvo que el proyecto o el usuario digan otra cosa; respetar el stack existente si ya hay uno.
- **Entorno**: comprobar JDK, Android SDK, Gradle (`./gradlew --version`), `adb`, Maestro (`maestro --version`) y dispositivos con `python scripts/devices.py`. Lo que falte es una pregunta de la fase 2 (instalar Maestro es una acción del usuario o con su permiso).
- **Rama**: proponer trabajar en una rama (`feature/impl-design`) con commits por pantalla; es pregunta de la fase 2 (nunca commit ni push sin que el usuario lo autorice).

### 1. Análisis profundo (diseño + código)
1. `python scripts/cobertura_diseno.py design/canvas --out impl/cobertura.md` genera la lista de **todas** las pantallas, variantes (prop `v` y otras como `mode`, `os`), tableros adaptativos, flujos e idiomas del lienzo. Es el punto de partida, no reemplaza leer.
2. Leer **cada** tablero `.dc.html` completo y cada ficha de `design/pantallas/`: medidas, tokens, tipografía, espaciados, íconos, textos (clave en `strings/en.json`), estados, comportamientos y su disparador, transiciones, accesibilidad (etiquetas, orden de foco, `aria-live`), y las reglas de teléfono/tablet/horizontal/claro/oscuro/RTL.
3. Leer **todo** el código actual (cada archivo, clase y método): qué existe, qué se reutiliza, qué hay que reescribir. Anotar la deuda técnica que afecta la implementación.
4. **Brechas**: para cada elemento del diseño, ¿qué hace falta en código (datos, API del sistema, permiso, migración, servicio)? ¿Es factible en la plataforma y con los datos que hay? Lo dudoso va a la fase 2.
5. **Interfaces externas**: listar todo lo que la app no controla (hardware como Bluetooth/cámara/sensores, otro equipo como una PC o un TV, red/servidores, base de datos con datos reales, tiempo, permisos y diálogos del sistema, notificaciones, servicios de Google). Para cada una, investigar la interfaz real (documentación oficial, especificación, comportamiento observado) y definir su **doble real** (`references/dobles-reales.md`).
6. Cierre: `impl/analisis.md` completo y `impl/cobertura.md` con todas las filas.

### 2. Preguntas (todo se resuelve ANTES de programar)
1. Escribir `impl/preguntas.md` con `templates/preguntas.md`. Siempre incluir:
   - Cada elemento del diseño **no factible** o factible solo en parte (con alternativas concretas y la recomendada). Nunca simplificar en silencio.
   - Contradicciones entre el diseño y el código o entre tableros.
   - Arquitectura y librerías: mantener lo existente o migrar (DI, navegación, persistencia); versión mínima de Android; si se agregan análisis estático, tests de captura u otras prácticas de `references/arquitectura.md` §Extras.
   - Rama, commits por pantalla y si se hace push (y a qué remoto).
   - Dispositivos: cuáles hay, si se pueden usar emuladores ya creados (nunca se crean nuevos), si se puede instalar/desinstalar la app en ellos (borra datos).
   - Datos: migraciones de la base de datos y si hay usuarios con datos reales que conservar.
   - Lo que el QA necesita del mundo real (una PC, un TV, una cuenta) y que se probará con el doble real si no está.
   - Lo necesario para Google Play que no sale del código: política de privacidad, firma, `applicationId`, ícono definitivo, ficha.
2. Preguntar con `AskUserQuestion` (hasta 4 por vez, la recomendada primero); si son muchas, también se pueden responder editando el archivo. Anotar cada respuesta en `preguntas.md` y `decisiones.md`.
3. Repetir hasta que no quede **ninguna** pregunta abierta.
4. Antes de arrancar, un resumen corto: pantallas y variantes, dobles reales, tests y flujos previstos, dispositivos, duración estimada. Desde aquí no se vuelve a preguntar.

### 3. Plan y cimientos
- `impl/plan.md` (`templates/plan.md`): arquitectura (`references/arquitectura.md`), paquetes/módulos, el mapa pantalla → ViewModel → casos de uso → repositorios → fuentes de datos, los puertos de cada interfaz externa con su adaptador real y su doble, el orden de implementación (cimientos → flujo principal → secundarios → adaptativo → idiomas) y la lista de tests y flujos Maestro.
- Cimientos primero, en este orden: tema (tokens claro/oscuro del diseño, tipografía, formas, movimiento), componentes del sistema de diseño, navegación, inyección de dependencias, puertos + adaptadores reales + dobles reales con su panel de pruebas (solo en debug), migraciones, textos (`values-*/strings.xml` de `design/strings/`).

### 4. Implementación (autónoma)
- Pantalla por pantalla, en el orden del plan. Para cada una:
  1. Estado de UI inmutable + eventos (UDF) en el ViewModel; lógica en casos de uso/dominio, no en la UI.
  2. La UI fiel al diseño: medidas, tokens, textos por clave, íconos, **todos** los estados y comportamientos (cada diálogo, hoja, menú, snackbar con deshacer, deslizable, transición), con `testTag` estables para Maestro.
  3. Adaptativo según el diseño: teléfono vertical/horizontal, tablet vertical/horizontal (clases de tamaño de ventana; en tablet el layout del diseño, nunca el teléfono estirado), claro/oscuro, RTL, fuente grande.
  4. Previews de Compose de cada estado (claro/oscuro, teléfono/tablet).
  5. Unit tests de la lógica que lo merece y su happy path de humo (`references/tests.md`).
  6. `./gradlew` compila, tests y lint en verde. Marcar en `impl/cobertura.md` y `impl/progreso.md`; commit si se acordó.
- **Pruebas en dispositivo cuando convenga** (al terminar el flujo principal, cada flujo grande y al final): instalar el debug, correr los flujos Maestro de lo hecho, revisar capturas y `logcat` (crashes, ANR, StrictMode). Ver `references/dispositivos.md`.
- **Si el dispositivo se desconecta**: no detenerse. Lanzar en segundo plano `python scripts/devices.py --wait --interval 600` (avisa al volver a haber un dispositivo; reintenta cada 10 minutos), anotarlo en `progreso.md` y **seguir implementando todo**. Las pruebas pendientes se acumulan en `progreso.md` y se corren apenas vuelva un dispositivo. Si no vuelve, el usuario lo resolverá; el código se termina igual.
- **Dudas durante la ejecución**: decidir lo más conservador y coherente con el diseño y lo ya decidido (nunca recortar el diseño ni inventar funciones), anotarlo en `decisiones.md` como "decisión propia, revisar" y seguir. Solo se para ante un bloqueo real (sin SDK, el proyecto no compila por causas externas) y se deja el motivo en `progreso.md`.
- Trabajos largos: el usuario puede lanzarlo con `/loop` (sin intervalo); cada vuelta retoma desde `impl/progreso.md`.

### 5. Automatización Maestro
- Seguir `references/maestro.md`. **Todas las pantallas** tienen al menos un flujo que llega a ellas y comprueba lo esencial; **no** se automatiza cada opción: cada flujo recorre varias cosas en una pasada. El **núcleo** de la app (su funcionalidad principal) tiene más cobertura: caminos alternativos, errores y recuperación.
- Los flujos usan los dobles reales (escenarios por enlace de prueba) para no depender de hardware ni de otro equipo; donde hay hardware real disponible, una etiqueta `real` marca los flujos que lo usan.
- Cada flujo es **independiente** (limpia y prepara su propio estado), así se reparte en paralelo: `python scripts/maestro_paralelo.py .maestro` usa todos los dispositivos conectados.
- Cubrir también horizontal, tablet (si hay un dispositivo o emulador de tablet), oscuro y al menos un idioma largo y uno RTL.

### 6. QA y preparación para producción
- Tomar el rol de QA (`references/qa.md`): no basta con que "funcione". Probar con Maestro y a mano (capturas) la funcionalidad, la usabilidad, la fidelidad al diseño, la accesibilidad, la robustez (rotación, muerte del proceso, sin permisos, sin conexión, Bluetooth apagado, datos vacíos y muchos datos), el rendimiento y los crashes.
- Cada bug: registrarlo en `impl/qa-informe.md`, corregir la causa raíz, agregar el test o flujo que lo habría detectado, volver a probar.
- Compilar el **release** (R8/minify activado) y correr el humo de Maestro sobre él: muchos errores solo aparecen ahí.
- Lista de Google Play de `references/qa.md` (targetSdk vigente, permisos justificados, seguridad de datos, política de privacidad, AAB, versionado, 64 bits, ícono adaptativo, sin logs sensibles).
- `impl/qa-informe.md` termina con un veredicto: **listo para producción** o la lista exacta de lo que lo impide.
- Mensaje final al usuario: corto, con el veredicto, lo implementado (pantallas, variantes, tests, flujos), los dobles reales, las decisiones propias a revisar y lo que queda en manos del usuario (firma, ficha, publicación; para publicar están los skills `android-release` y `play-console`).

## Cobertura del pedido original

Cada punto del pedido que dio origen a este skill y dónde se cumple:

| Pedido | Dónde |
|---|---|
| Implementar todas las pantallas al 100 %, sin omitir nada | Regla 1, fase 1 (`cobertura.md`), fase 4, fase 6 (matriz completa) |
| Si algo no es factible, preguntar al principio y resolverlo | Fase 1 paso 4, fase 2 |
| Resolver todo al principio y luego trabajar solo toda la noche | Regla 2, fase 2 punto 4, fase 4 |
| Todo el detalle del diseño en tablet/teléfono, claro/oscuro, horizontal/vertical | Fase 4 puntos 2-4, `arquitectura.md` §Adaptativo |
| Unit tests de la lógica crítica y compleja, inteligentes, sin tests inservibles | Fase 4 punto 5, `tests.md` |
| Happy path básico por pantalla para evitar crashes obvios | `tests.md` §Humo, fase 5 |
| Maestro en todas las pantallas, varias cosas por pasada, más en el núcleo | Fase 5, `maestro.md` |
| Probar en el teléfono conectado cuando convenga | Fase 4, `dispositivos.md` |
| Si se desconecta, no parar: terminar la implementación y reintentar cada 10 minutos | Regla 3, fase 4, `devices.py --wait --interval 600` |
| Usar un emulador si ya está configurado, sin crear emuladores | `dispositivos.md` |
| Maestro en paralelo en varios dispositivos | Fase 5, `maestro_paralelo.py`, `maestro.md` §Paralelo |
| Rol de QA: funcionalidad, usabilidad, UI/UX, listo para producción | Fase 6, `qa.md` |
| Dobles reales (un teléfono, un registro en la base, una PC Bluetooth HID) investigando las interfaces reales | Regla 4, fase 1 paso 5, `dobles-reales.md` |
| Que los dobles no bloqueen la automatización | `dobles-reales.md` §Escenarios, `maestro.md` |
| App 100 % funcional, lista para Google Play | Fase 6, `qa.md` §Google Play |
| Arquitectura y buenas prácticas móviles, patrones de diseño, clean code, SOLID | Regla 5, `arquitectura.md` |
| Código de alta calidad, mantenible por alguien sin IA | `arquitectura.md` §Mantenible por personas |

## Errores que hay que evitar
- Empezar a programar con preguntas abiertas, o preguntar a mitad de la noche.
- "Simplificar" una pantalla, omitir un estado o un comportamiento, o dejar un TODO en lugar de implementarlo.
- Textos fijos en el código, colores o medidas sueltas en lugar de tokens, el tablet como teléfono estirado.
- Detenerse porque no hay dispositivo, o crear un emulador nuevo.
- Tests que solo repiten la implementación (getters, mapeos triviales, mocks de todo) o que nunca fallarían.
- Flujos Maestro que dependen unos de otros, del orden o de hardware real sin etiqueta; `sleep` fijos en lugar de esperas por condición.
- Dobles reales que se cuelan en el build release.
- Dar por terminado sin el QA, sin probar el release minificado o sin el veredicto de producción.
