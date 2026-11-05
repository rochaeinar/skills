# La app y su web, integradas

Cada web de una app cierra el círculo con la app y con Google Play. **No queda nada suelto:**

| Dónde | Qué tiene que haber |
|---|---|
| **App › Acerca de** | Versión, **enlace al sitio** (abre el navegador) y los documentos **Política de privacidad**, **Términos y condiciones** y **Licencias de terceros**, mostrados en Markdown dentro de la app |
| **App › assets/legal/** | `privacy.md`, `terms.md`, `licenses.md`, **solo en inglés**: la **única fuente** de los textos |
| **Web** | `/privacy/` (obligatoria para Play) y `/terms/`, copias exactas de los de la app (`web.py legal`), en inglés en todos los idiomas del sitio |

**Regla: los documentos legales van SOLO en inglés, en la app y en la web, y nunca se traducen** (un único texto que vale, sin versiones que puedan contradecirse). Lo que sí se traduce es la interfaz alrededor: las etiquetas de Acerca de ("Política de privacidad"…) y, en la web, el título y el enlace de volver.
| **Play** | `<carpeta de la app>/play/app-content.md`: la URL de la política de privacidad, el sitio web y las respuestas de "Contenido de la app" |

Orden: análisis (SKILL.md paso 1) → **documentos** → **Acerca de en la app** → web → `web.py legal` → deploy → `web.py legal --check --online`.

---

## 1. Antes de escribir: qué tiene la app

Leer el código, no suponer. Anotar en `content/analysis.md` (sección "Integración con la app"):

- **Pila de interfaz:** Compose (`@Composable`, `setContent`) o Views (layouts XML, Fragments/Activities); Kotlin o Java (`app-design-implementation`: si el proyecto es solo Java, escribir en Java con el mismo diseño).
- **Acerca de existente:** buscar `About`, `Acerca`, `about_`, `version`, `privacy`, `licen` en el código y en `res/values/strings.xml`. Puede ser una pantalla, un diálogo, una sección de Ajustes o nada. Textos legales ya escritos (un `privacy_body` en un diálogo, un `LICENSE.md` en assets, `OssLicensesMenuActivity` de Google): se **reemplazan** por los documentos Markdown, para que haya una sola fuente; antes, leerlos y conservar lo que siga siendo verdad.
- **Navegación:** Navigation Compose (rutas tipadas, `NavHost`), un `enum` de pantallas, Fragments con un navegador propio o Activities. Las pantallas nuevas siguen el mismo mecanismo; nunca mezclar dos.
- **Tema:** tokens propios (un objeto de colores, `LocalXxxColors`) o `MaterialTheme`; claro/oscuro; fuentes. Las pantallas nuevas usan esos tokens.
- **Idiomas:** las carpetas `res/values-*` (todas reciben las etiquetas traducidas) y `localeFilters`/`resConfigs` en Gradle.
- **Markwon:** si ya está en las dependencias, reutilizar su versión.
- **Desarrollador:** el nombre de la cuenta de Play (perfil del sitio). Si `accounts.json` tiene `"developer"` en el perfil, usar ese; si no, preguntarlo una vez y guardarlo ahí.

## 2. Los documentos (análisis, no copiar y pegar)

Plantillas en `templates/android/legal/` (solo inglés). Cada sección trae, en un comentario, **qué hay que verificar en el código**. Son documentos importantes: cada afirmación se comprueba, se anota la evidencia en el análisis y el resultado se redacta para esta app. Una sección que no aplica se reescribe o se quita; nunca queda texto de ejemplo.

### Qué revisar para la privacidad y los términos
| Tema | Dónde mirarlo |
|---|---|
| Permisos | El manifiesto **final**: `app/build/intermediates/merged_manifests/release/**/AndroidManifest.xml` después de `assembleRelease`, o `aapt2 dump permissions <apk>`. Incluye los que agregan las librerías y los quitados con `tools:node="remove"` |
| Internet y servidores | Permiso `INTERNET`; `grep -rn "https\?://"` en el código y en `res`; clientes HTTP (OkHttp, Retrofit, Ktor, Volley); `google-services.json` |
| SDK de terceros | `web.py licenses <slug>` (todas las dependencias del release) y la inicialización en `Application`/`ContentProvider` (Firebase, Crashlytics, Analytics, AdMob, Billing, Maps, Drive…) |
| Anuncios y compras | `com.google.android.gms:play-services-ads`, `com.android.billingclient`; el ID de AdMob en el manifiesto → `public/app-ads.txt` en la web |
| Qué se guarda | Bases de datos (Room, SQLite, data-access), `SharedPreferences`/DataStore, archivos; qué tablas y campos |
| Respaldo de Android | `android:allowBackup`, `fullBackupContent`, `dataExtractionRules` y sus XML en `res/xml`: qué entra en la copia de Google |
| Registros | El logger de la app: qué escribe, si redacta datos sensibles, si sale del teléfono |
| Contenido sensible | Lo que el usuario escribe, ubicación, contactos, cámara, micrófono, salud: decir explícitamente qué pasa con cada uno |
| Público y edad | Preguntar al usuario qué declaró (o declarará) en Play Console; la misma edad en privacidad, términos y `app-content.md` |
| Usos que la política de Play vigila | Automatización, control de otros equipos, accesibilidad, VPN, ubicación en segundo plano: los Términos dicen el uso aceptable |

### Licencias de terceros
1. `web.py licenses <slug>` corre Gradle en el proyecto de la app (`releaseRuntimeClasspath`), lee la licencia del POM de cada artefacto (siguiendo los POM padre) y escribe `content/licenses-inventory.md`: componente, versión, licencia, URL y lo que no se pudo resolver.
2. Completar a mano lo que Gradle no ve: módulos locales (`project(':lib')`) con su propia licencia, `.aar`/`.jar` en `libs/`, fuentes (`res/font`, `assets/fonts`: casi siempre OFL 1.1), íconos (Material Symbols: Apache 2.0), sonidos, imágenes y datos de terceros.
3. Solo lo que **va en la app**: las dependencias de test y de compilación (JUnit, Espresso, Robolectric, lint, KSP, kapt) no se distribuyen.
4. Apache 2.0 en una tabla (componente · autor). MIT, BSD, ISC, EPL, MPL, OFL, CC-BY: una sección por licencia con el componente, la versión, el titular del copyright y el **texto completo** (MIT/BSD/ISC exigen reproducir el aviso), tomado del `LICENSE` del proyecto.
5. Sin licencia encontrada, o copyleft (GPL, LGPL, AGPL): avisar al usuario antes de publicar.

### Formato y archivos
- `app/src/main/assets/legal/privacy.md`, `terms.md`, `licenses.md`: **un archivo por documento, en inglés**. Nunca `privacy_es.md` ni otra traducción (`web.py legal` las rechaza); si la app traía traducciones, se borran.
- Cabecera: `**App** · Desarrollador` + fecha de actualización en cursiva; `---`; secciones `## 1. …` numeradas; tablas para permisos, servicios y licencias; contacto al final con el enlace al sitio.
- Fecha de actualización: la del día en que cambia el contenido (no la del build).
- Markdown simple (CommonMark + tablas): lo muestran igual Markwon en la app y Astro en la web. Sin HTML.
- No es asesoría legal: el usuario revisa los textos antes de publicar (decirlo al entregarlos).

## 3. Acerca de en la app

### Diseño (igual en Views y Compose)
- **Identidad:** el ícono de la app (84 dp, esquinas redondeadas o su fondo adaptativo), el nombre (24 sp, negrita), "Versión X (N)" (13 sp, secundario).
- **Sitio web:** una píldora con borde (44 dp de alto, radio 22 dp): ícono de globo, el dominio en el color de acento y en negrita, flecha "abre fuera". Abre el navegador con `Intent.ACTION_VIEW`; sin navegador, no falla.
- **"Legal e información":** encabezado en mayúsculas (12 sp, negrita, secundario) y una tarjeta (radio 18 dp, borde de 1 dp) con una fila por documento: mosaico de 36 dp con el ícono teñido de acento al 12 %, título (15 sp), chevron. Filas de al menos 56 dp; divisores alineados después del mosaico (66 dp).
- **Desarrollador** abajo: "Desarrollado por **X**" y "© año X" (11 sp, terciario).
- Contenido de 480 dp como máximo, centrado: en tablet y en horizontal conserva las proporciones del teléfono y se desplaza si no entra.
- **Documento:** barra con atrás y el título; el Markdown de 15 sp con 4 dp de interlineado, 20 dp de margen y 680 dp de ancho máximo; enlaces, viñetas y citas en el acento; bordes de tabla y líneas en el color de divisor. Se lee y se procesa fuera del hilo principal.
- Claro y oscuro con los colores de la app; RTL (los chevrons y la flecha atrás se espejan, `autoMirrored`); TalkBack: encabezados marcados, los íconos decorativos sin descripción, el enlace web con descripción.
- Bordes a borde (targetSdk 35+): las barras del sistema no tapan nada (insets).

### Plantillas (`templates/android/`)
| Archivo | Para | Qué es |
|---|---|---|
| `common/LegalDocs.kt` | todas | La ruta `assets/legal/<doc>.md` de cada documento (inglés, sin elegir idioma) y su lectura segura |
| `common/MarkdownRenderer.kt` | todas | Markwon con tablas, tachado y enlaces automáticos; colores del tema |
| `compose/AboutDocuments.kt` | Compose | `AboutScreen` completa, o sus piezas `WebsiteLink` y `LegalDocumentsCard` para un Acerca de existente, y `MarkdownDocumentScreen` |
| `views/AboutActivity.kt`, `MarkdownActivity.kt`, `MaxWidthLinearLayout.kt`, `views/res/layout/*` | Views | Las dos pantallas como Activities (pasarlas a Fragments si la app navega con Fragments) |
| `res/drawable/*` | todas | Íconos de trazo de 24 dp (privacidad, términos, licencias, web, externo, chevron, atrás) y fondos de tarjeta, mosaico y píldora |
| `res/values*/about_strings.xml` | todas | Etiquetas (en, es) y los enlaces del sitio: `about_web_label`, `about_web_url`, `privacy_policy_url` |
| `res/values*/about_colors.xml`, `about_styles.xml` | Views | Colores derivados de la paleta de la app (claro y oscuro) y el divisor |

Pasos:
1. Reemplazar `{{PACKAGE}}` por el paquete de la app (o el paquete de UI que use: `<paquete>.ui.about`) y adaptar a la arquitectura: si la app tiene ViewModels, inyección de dependencias, un logger o un contenedor, usar los suyos; si sus pantallas tienen componentes propios (barra superior, botones, tarjetas), usarlos en vez de los genéricos. **El resultado tiene que verse como parte de la app**, no como un agregado.
2. Gradle: `io.noties.markwon:core`, `ext-strikethrough`, `ext-tables`, `linkify`, todos **4.6.2** (en el catálogo de versiones si la app lo usa). Ya traen sus reglas de R8.
3. Etiquetas traducidas a **todos** los idiomas de la app (naturales; las de idiomas con pocos recursos, marcadas para revisión nativa). `about_web_*` y `privacy_policy_url` no se traducen.
4. Entrada a Acerca de: desde Ajustes o el menú principal, donde la app ya ponga lo secundario. Atrás del sistema vuelve de un documento a Acerca de y de Acerca de a donde estaba: con Navigation es automático; si la app navega con estado propio, `BackHandler` en cada pantalla nueva (un atrás que cierra la app es un error). Si ya había un Acerca de, se le agregan el sitio y la tarjeta de documentos y se quitan los diálogos legales viejos.
5. Las pantallas nuevas también entran en los flujos de prueba de la app: si tiene Maestro, un flujo de humo "Acerca de → cada documento se abre → atrás"; si tiene tests de UI, lo mismo.

### Comprobar en el dispositivo
`./gradlew installDebug` (o la variante que use la app) y en el teléfono o el emulador: Acerca de en claro y oscuro, el enlace abre el sitio, cada documento se abre con sus tablas y enlaces (en inglés aunque la app esté en otro idioma), en horizontal y con letra grande. Revisar las capturas con Read. Release: `assembleRelease` sin errores de R8.

## 4. Web y Play

- `web.py legal <slug>` copia `privacy.md` y `terms.md` de la app a `src/legal/<doc>.md` (la misma página en inglés, marcada `lang="en"`, para todos los idiomas del sitio), quita las plantillas y las copias por idioma que quedaron sin usar (p. ej. créditos de imágenes si la app no tiene), comprueba que la app enlace el dominio (`about_web_url`, `privacy_policy_url`) y que use los documentos, y crea o actualiza `play/app-content.md` con los enlaces. Las respuestas de "Seguridad de los datos" las completa Claude desde el análisis.
- La carpeta de Play: `site.json › play_dir` (la pone `new`: la registrada por `play-console` para el paquete, o `<carpeta de la app>/play`).
- Después del deploy de producción y del dominio: `web.py legal <slug> --check --online` (la URL de privacidad responde 200 con el texto de la app).
- Cada cambio de un documento: editar el de la app → `web.py legal` → `build` → `deploy`; y una versión nueva de la app (`android-release`).
