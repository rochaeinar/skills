# De dónde salen las reglas del CLAUDE.md base

Recopiladas de los `CLAUDE.md` de las apps del usuario (Bible Versions en Java, Forever Note en Kotlin, Solid Tracker en Java) y de lo que se aprendió con Keyboard & Mouse. `templates/claude/CLAUDE.md` las lleva todas; esta tabla dice por qué existe cada una, para poder defenderla o adaptarla.

| Regla | Visto en | Por qué |
|---|---|---|
| Firma sin contraseñas en disco: Administrador de credenciales + variables de entorno; el debug firmado con la clave de release | bible-versions, forever-note (`SIGNING.md`, `setup-signing.ps1`) | Google Sign-In / Drive funcionan en desarrollo y el debug se instala encima del de Play sin borrar datos |
| Clave fuera del repo, en la carpeta de la app | bible-versions (`D:/Documents/BibleVersions/KeyStore`), forever-note | Un `.jks` en git es una fuga permanente |
| Regla de bugs: todo arreglo con un test de regresión que falla antes y pasa después, en JVM con JUnit 4 sin Mockito; extraer la lógica a una clase pura con interfaz | bible-versions (obligatoria, skill `bugfix`) | Los crashes de Play vuelven si no hay un test que los fije |
| Clean code: nombres que explican, métodos cortos, retornos tempranos, 2-3 niveles de anidación, sin números mágicos, sin comentarios que repiten el código | tracker (Clean Code de Robert C. Martin, política de comentarios) | El código lo mantienen personas sin IA |
| Las pantallas solo cablean; cada función en su clase o paquete ("si agregas lógica a este archivo, para y crea la clase correcta") | forever-note (`RichEditText` y `NoteEditFragment` limpios) | Evita clases de miles de líneas |
| Nada de llamadas a la base fuera de los repositorios; los campos de sync solo por métodos del repositorio (`saveNew`, `saveUpdated`, `markDeleted`) y con los enums `ItemStatus` / `SyncStatus` | forever-note, tracker | Un campo de sync puesto a mano rompe la sincronización con Drive |
| DAL, no Room; tabla nueva = versión nueva + migración explícita | forever-note, tracker, data-access | Las librerías propias son la base común de todas las apps |
| Librerías propias como módulos de fuente | bible-versions, forever-note, tracker, keyboard-and-mouse | Depurar y corregir en la librería |
| Logs sin datos sensibles; release en `warn`, sin `rest` ni `overlay` | app-design-implementation (librerías propias), RestLog | Privacidad y Data safety de Play |
| adb fuera del PATH; `MSYS_NO_PATHCONV=1` en Git Bash; respaldar datos antes de tocarlos en el teléfono; `uiautomator dump` para coordenadas | bible-versions (Device Testing) | Errores reales que costaron tiempo |
| Maestro: por `id`, subflujo de inicio común, nunca `clearState`, `inputText` ASCII, enlaces de prueba solo en debug | bible-versions (`.maestro/README.md`), keyboard-and-mouse | Flujos estables y que no borran los datos del usuario |
| Credenciales solo en el Administrador de credenciales, escritas en una ventana aparte | bible-versions (CDN), todos los skills | Nunca en el chat ni en archivos |
| Textos en `strings.xml`, inglés en `values/`; documentos legales solo en inglés | keyboard-and-mouse, cloudflare-site | 30 idiomas sin textos sueltos; los legales no se traducen |
| Commit solo si el usuario lo pide; push nunca sin preguntar | todos los skills | El usuario controla su historial |
| Lenguaje: nuevo → Kotlin; Java sigue Java; híbrido → lo nuevo en Kotlin | app-design-implementation | Coherencia del proyecto |

Lo específico de cada app (formato RTF de Forever Note, FCM y SMS de Tracker, módulos bíblicos) **no** va al base: queda en el `CLAUDE.md` de esa app.
