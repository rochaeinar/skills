# Políticas de Google y restricciones de implementación

Se hace en la fase 1 (paso 6), **antes de programar**, y se repasa en la fase 6. Las políticas de Google Play y los requisitos de Android cambian varias veces al año: **nunca de memoria**. Cada punto se comprueba en la documentación oficial vigente con `WebSearch` (modo `extended` para lo reciente) y `WebFetch`, y se anota la URL y la fecha de consulta.

## Fuentes oficiales
- Centro de políticas para desarrolladores de Google Play: `https://support.google.com/googleplay/android-developer/` (Developer Program Policies) y el anuncio de cambios de política más reciente.
- Requisito de API de destino (`targetSdk`) y sus fechas.
- `https://developer.android.com/about/versions/<versión>/behavior-changes-all` y `behavior-changes-<versión>` de cada versión entre `minSdk` y el `targetSdk`.
- La documentación de cada API que usa la app (p. ej. `BluetoothHidDevice`, servicios en primer plano, notificaciones).
- Requisitos de Play Console: Data safety, declaración de permisos, tipos de servicio en primer plano, eliminación de cuentas.

## Qué revisar (cada uno contra el diseño y el código)

| Tema | Qué buscar |
|---|---|
| `targetSdk` exigido | La API de destino que Play exige hoy para apps nuevas y actualizaciones, y los cambios de comportamiento que trae (p. ej. edge-to-edge obligatorio, servicios en primer plano, intents implícitos). |
| Requisitos técnicos | Páginas de memoria de 16 KB para código nativo, AAB, 64 bits, tamaño. |
| Permisos restringidos | SMS y registro de llamadas, `QUERY_ALL_PACKAGES`, ubicación en segundo plano, `MANAGE_EXTERNAL_STORAGE`, fotos y videos, `SCHEDULE_EXACT_ALARM`/`USE_EXACT_ALARM`, `USE_FULL_SCREEN_INTENT`, instalar paquetes, `SYSTEM_ALERT_WINDOW`. Cada uno exige un uso principal permitido y, muchas veces, una declaración en Play Console. |
| Servicios en primer plano | El tipo correcto (`connectedDevice`, `dataSync`, `mediaPlayback`…), su permiso específico, la declaración con video en Play Console y que la tarea realmente lo necesite. |
| API de accesibilidad | Solo para ayudar a personas con discapacidad o con la declaración de uso aceptado; nunca para automatizar otras apps sin ese fin. |
| Bluetooth / dispositivos | Permisos de Android 12+ (`BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` con `neverForLocation`, `BLUETOOTH_ADVERTISE`), perfiles que dependen del fabricante (p. ej. HID Device), visibilidad. |
| Datos del usuario | Data safety coherente con lo que hacen la app **y sus librerías** (RestLog, synchronizer, crashes, anuncios); política de privacidad; divulgación destacada y consentimiento antes de recoger datos sensibles; eliminación de la cuenta y los datos desde la app y desde la web si hay cuentas. |
| Comportamiento engañoso y abuso | Funciones que prometen algo que no hacen, imitar apps del sistema, interferir con otras apps o con el dispositivo, teclados o inyección de entrada en otros equipos sin control del usuario. |
| Propiedad intelectual e imitación | Nombres, íconos o marcas de terceros (Windows, Mac, Bluetooth, Google) usados como si fueran la app o con su aval; las marcas nominativas permitidas solo para describir compatibilidad. |
| Pagos y anuncios | Bienes digitales solo con Google Play Billing; anuncios según la política (sin anuncios de pantalla completa sorpresa, nada en notificaciones), familias e infancia si el público lo incluye. |
| Contenido y público | Clasificación de contenido, público objetivo (si incluye niños → política de Familias). |
| Funciones del diseño no permitidas | Todo lo que el diseño muestra y Android o Play no permiten (abrir ajustes del sistema que ya no existen, acciones en segundo plano bloqueadas, leer datos de otras apps). |

## Cómo se anota

En `impl/analisis.md` §Políticas, una fila por tema revisado (también los que están bien):

| Tema | Fuente (URL, fecha) | Qué hace la app | Riesgo | Soluciones |
|---|---|---|---|---|

Cada riesgo pasa a `impl/preguntas.md` con 2-3 soluciones concretas y la recomendada, por ejemplo: usar un permiso menos sensible o una API alternativa, pedir el permiso solo en el momento de uso con una explicación, agregar la divulgación y el consentimiento, preparar la declaración de Play Console (con el texto y el video que pide), cambiar o quitar la función. Nunca se programa una función con un riesgo de política abierto.

## En la fase 6
Repetir la búsqueda de cambios publicados desde la fase 1, revisar el manifiesto del release (permisos de la app y de las librerías) contra la tabla, y dejar en `impl/qa-informe.md` las declaraciones de Play Console que el usuario tiene que completar, con el texto propuesto.
