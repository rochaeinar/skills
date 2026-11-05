# Plan de implementación — <App>

## Arquitectura
- Capas y paquetes (ver `references/arquitectura.md`), módulos Gradle, DI, navegación, persistencia.
- Decisiones de arquitectura (ADR cortos): contexto → decisión → consecuencia.

## Mapa por pantalla
| Pantalla (tablero) | Route / Screen / ViewModel | Casos de uso | Repositorios / puertos | Estados | Tablet / horizontal |
|---|---|---|---|---|---|

## Interfaces externas
| Externo | Puerto | Adaptador real | Doble real | Fallos simulables | Fuente de la investigación |
|---|---|---|---|---|---|

## Escenarios de prueba (dobles reales)
| Escenario | Datos | Estado de los dobles | Usado por |
|---|---|---|---|

## Orden
1. Cimientos: tema, componentes, navegación, DI, puertos + dobles + panel de pruebas, migraciones, textos
2. Flujo principal (núcleo)
3. Flujos secundarios
4. Adaptativo (horizontal, tablet)
5. Idiomas, RTL, accesibilidad
6. Maestro completo · 7. QA y release

## Tests previstos
| Lógica | Por qué protege algo | Tipo (unit / contrato / migración / humo) |
|---|---|---|

## Flujos Maestro previstos
| Flujo | Etiquetas | Pantallas que recorre | Qué comprueba |
|---|---|---|---|
