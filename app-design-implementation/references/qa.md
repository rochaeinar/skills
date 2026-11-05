# QA: listo para producción

En la fase 6 el rol es el de un **QA exigente**, no el del programador que defiende su código. La pregunta no es "¿funciona?", sino "¿lo publicaría hoy en Google Play para millones de usuarios?".

## Qué se prueba

**Funcionalidad**
- Cada fila de `impl/cobertura.md`: la pantalla y sus variantes existen y se comportan como el diseño.
- El núcleo de punta a punta con el doble real (y con hardware real si está): el efecto llega al otro lado (p. ej. lo escrito aparece en la PC virtual).
- Errores y recuperación: cada mensaje de error del diseño aparece en su situación real y su salida funciona.

**Usabilidad y UI/UX**
- Fidelidad al diseño: comparar capturas de Maestro con los tableros (espaciados, tipografía, colores, íconos, textos) en claro y oscuro, teléfono y tablet, vertical y horizontal.
- ¿Se entiende sin explicación? ¿Cada pantalla tiene cómo volver? ¿El botón atrás hace lo esperado? ¿Hay callejones sin salida, pasos de más, textos ambiguos?
- Retroalimentación: cada acción muestra su resultado (carga, éxito, error), nada es silencioso.
- Objetivos táctiles, legibilidad, contraste, foco y TalkBack en el núcleo.

**Robustez**
- Rotación y cambio de tamaño en medio de tareas; muerte del proceso (`adb shell am kill` con la app en segundo plano) y regreso.
- Sin permisos, permisos revocados en ajustes, "no volver a preguntar".
- Sin conexión / Bluetooth apagado / equipo remoto que desaparece.
- Datos: vacíos, muchos, textos largos, caracteres especiales, emojis, RTL.
- Idiomas: textos que no caben, plurales, formatos de fecha y número.
- Fuente al 200 %, modo oscuro del sistema cambiando con la app abierta.

**Estabilidad y rendimiento**
- Cero crashes y ANR en `logcat` durante toda la pasada; StrictMode sin violaciones en el núcleo; LeakCanary sin fugas (si está).
- Arranque y listas fluidas; nada pesado en el hilo principal.

**Release**
- `./gradlew assembleRelease`/`bundleRelease` con R8: instalar (firmado con la clave de debug si no hay otra) y correr el humo de Maestro (`release/`). Revisar reglas de ProGuard (Room, serialización, reflexión).
- Los dobles reales y el panel de pruebas no están en el release (buscar las clases en el APK con `apkanalyzer` o en el mapping).

## Google Play

- `targetSdk` en la versión que exige Google Play hoy (comprobarlo en la documentación vigente), `minSdk` acordado.
- AAB, `versionCode`/`versionName` correctos (el skill `android-release` los calcula al publicar).
- Permisos: solo los necesarios, cada uno con su explicación en la app; permisos especiales (servicio en primer plano y su tipo, Bluetooth, notificaciones) declarados y justificados para el formulario de Play.
- Seguridad de los datos (Data safety) coherente con lo que la app hace; política de privacidad si se recogen o comparten datos.
- Ícono adaptativo y monocromo, nombre, pantalla de inicio (splash API).
- Sin logs de depuración con datos, sin claves en el código, `debuggable` falso en release.
- Accesibilidad básica (el reporte previo al lanzamiento de Play la revisa) y compatibilidad de pantallas.

## Bugs

Cada bug en `impl/qa-informe.md` con: id, severidad (bloqueante / alta / media / baja), pantalla, pasos para reproducir, esperado vs. obtenido, captura o log, causa raíz, corrección, test o flujo agregado, verificado (sí/no). Se corrigen todos los bloqueantes, altos y medios; los bajos se corrigen salvo que el usuario decidió lo contrario.

## Veredicto

`impl/qa-informe.md` termina con **Listo para producción: sí / no**. Si es no, la lista exacta de lo que lo impide y quién lo resuelve (código, usuario, cuenta de Play).
