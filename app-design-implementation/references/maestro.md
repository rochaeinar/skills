# Automatización con Maestro

## Qué automatizar

- **Todas las pantallas**: al menos un flujo llega a cada pantalla y comprueba lo esencial (título, contenido principal, la acción principal y su resultado).
- **No** cada opción: un flujo recorre **varias cosas en una pasada** (abre un menú, cambia una opción, comprueba el resultado, deshace, sigue a la siguiente pantalla). Pocos flujos largos y con sentido, no cientos de flujos de un toque.
- **El núcleo de la app** (su funcionalidad principal) tiene más: caminos alternativos, errores y su recuperación, datos límite, rotación en medio de la tarea, y comprobación del efecto real en el doble (p. ej. lo que "escribió" la PC virtual).
- Variantes del entorno, al menos una pasada de: oscuro, horizontal, tablet (si hay dispositivo o emulador de tablet), un idioma largo (alemán) y uno RTL (árabe), fuente grande.

## Estructura

```
.maestro/
  config.yaml                 # flujos incluidos, etiquetas, orden si hace falta
  common/                     # subflujos: launch_clean.yaml, open_scenario.yaml, set_dark.yaml ...
  smoke/                      # 01-welcome.yaml ... un recorrido por pantalla (etiqueta smoke)
  core/                       # núcleo: más profundidad (etiqueta core)
  adaptive/                   # horizontal, tablet, oscuro, idiomas (etiqueta adaptive)
  real/                       # usan hardware real (etiqueta real; se excluyen por defecto)
  release/                    # humo sobre el build release (etiqueta release)
```

- Ids estables: `Modifier.testTag("home_connect")` con `testTagsAsResourceId = true` en la raíz; Maestro usa `id:`. Textos solo para comprobar textos.
- Subflujos con `runFlow` y parámetros (`env`) para no repetir.
- Esperas por condición (`extendedWaitUntil`, `assertVisible` con `timeout`), nunca `sleep` fijos; animaciones cortas en debug si hace falta.
- Capturas (`takeScreenshot`) en los puntos que el QA revisa contra el diseño.

## Independencia (requisito para el paralelo)

- Cada flujo empieza con `launchApp` + `clearState` (o `clearState: true`) y carga su escenario con el enlace de prueba (`openLink: myapp-test://scenario?...`, ver `dobles-reales.md`). Ningún flujo depende de otro ni del orden.
- Nada compartido entre dispositivos: cada uno tiene su app, sus datos y su doble real.
- Permisos: `launchApp` con `permissions` o el escenario los resuelve; los flujos de permisos denegados lo declaran explícitamente.

## Paralelo en varios dispositivos

- `python scripts/maestro_paralelo.py .maestro [--include-tags smoke,core] [--exclude-tags real]`: reparte los flujos entre todos los dispositivos conectados (`adb devices`), corre un proceso de Maestro por dispositivo (`--device <serial>`), junta los reportes JUnit y las capturas en `impl/maestro/<fecha>/` y resume.
- Alternativa nativa: `maestro test --shard-split <N> .maestro` (o `--shard-all` para correr todo en cada dispositivo, útil para comparar teléfono y tablet). Comprobar las opciones con `maestro test --help`, cambian entre versiones.
- Un solo dispositivo también funciona: el script corre todo en él.

## Resultados

- Cada fallo se analiza: ¿bug de la app (va a QA y se corrige), flujo frágil (se arregla el flujo) o entorno (dispositivo)? Nunca se "arregla" un fallo borrando el paso.
- Resumen en `impl/progreso.md` (y en `impl/qa-informe.md` en la fase 6): flujos, pasados/fallidos por dispositivo, capturas relevantes.
