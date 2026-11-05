<!--
PLANTILLA · Licencias de terceros (código abierto) (español). Leer antes references/app-integration.md.
Archivo final: <app>/app/src/main/assets/legal/licenses_es.md.
- Fuente de verdad: `web.py licenses <slug>` (content/licenses-inventory.md): cada artefacto del
  classpath de ejecución del RELEASE con la licencia que declara su POM. Agregar lo que Gradle no ve:
  módulos/AAR locales, fuentes en res/font o assets (OFL…), juegos de íconos, sonidos, imágenes,
  archivos de datos.
- Solo lo que VA en la app. Las herramientas de test y de compilación (JUnit, Espresso, Robolectric,
  lint, KSP…) no se distribuyen: quedan fuera.
- Los componentes Apache 2.0 van en una sola tabla (componente · autor). Cada otra licencia (MIT, BSD,
  ISC, OFL, EPL, MPL, CC-BY…) tiene su sección con el componente, la versión, el titular del
  copyright y el texto COMPLETO de la licencia (MIT/BSD/ISC exigen reproducir el aviso de copyright
  y de permiso; tomarlo del LICENSE del proyecto, no de memoria). Los textos legales de las licencias
  quedan en su idioma original (inglés). Fuentes OFL: nombre, línea de copyright y enlace a la OFL 1.1.
- Un componente sin licencia encontrada, o con licencia copyleft (GPL/LGPL/AGPL), se informa al
  usuario antes de publicar: puede ser incompatible con la distribución de la app.
- Reemplazar cada {{MARCADOR}} y borrar todos los comentarios.
-->
**{{APP}}** usa componentes y recursos de código abierto de terceros. Agradecemos a sus autores y a sus comunidades.

© {{YEAR}} {{DEVELOPER}}

---

## Resumen

| Componente | Licencia |
| --- | --- |
| {{N}} componentes (AndroidX, Kotlin, Google…) | Apache 2.0 |
| {{COMPONENTE}} | {{LICENCIA}} |

## Licencia Apache 2.0

Estos componentes se distribuyen bajo la [Licencia Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0):

| Componente | Autor |
| --- | --- |
| {{COMPONENTE}} | {{AUTOR}} |

El texto completo de la licencia está en [apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0).

## {{OTRA_LICENCIA}}

**{{COMPONENTE}}** {{VERSION}} · {{TITULAR}}

<!-- Para qué se usa, en pocas palabras, si ayuda. Después el texto de la licencia: -->

```
{{TEXTO_COMPLETO_DE_LA_LICENCIA}}
```

## Fuentes

<!-- Una línea por fuente: **Nombre** · copyright · [SIL Open Font License 1.1](https://openfontlicense.org).
  También las fuentes e íconos (p. ej. Material Symbols · Google · Apache 2.0, si no está arriba). -->
