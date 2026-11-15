# Pantallas de Play Console (las que no tienen API)

Cada pantalla es un archivo `<pantalla>.json` con pasos declarativos que `console.py run` ejecuta sobre el expediente **aprobado**. Ningún archivo trae selectores inventados: **se graban la primera vez (F0)** mirando la pantalla real y quedan en `"status": "draft"` hasta que una corrida en `--dry-run` y una real los validan; entonces pasan a `"verified"` con la fecha.

## Cómo se graba una pantalla (Claude, con el usuario mirando solo la primera vez)

1. `console.py whoami --profile <perfil>` (cuenta correcta).
2. Navegar a la pantalla y `console.py snapshot --profile <perfil> --name <pantalla>`: captura + árbol de accesibilidad (`.aria.yaml`, con roles y nombres exactos).
3. Escribir los pasos con los **roles y nombres del árbol** (nunca clases CSS ni posiciones). Consola en el idioma fijo de esa cuenta (`console_language` de la pantalla; Era Soft Labs: es-419).
4. `console.py run <pantalla> --app <carpeta> --dry-run`: llena sin guardar y deja la captura. Revisarla con Read.
5. Corrida real, con `readback` de cada campo. Si pasa: `"status": "verified"`, `"verified_at": "<fecha>"`.
6. Si Google cambia la pantalla, la corrida se detiene con captura y árbol: repetir 2-5 solo en esa pantalla.

## Pantallas necesarias

| Archivo | Pantalla de Play Console | Usa del expediente | Irreversible |
|---|---|---|---|
| `create_app.json` | Home > Create app (nombre, idioma, app/juego, gratis, declaraciones) | `name`, `default_language`, `type`, `free` | Sí (gratis no vuelve a pago) |
| `app_signing.json` | Protected with Play > Play Store protection > Manage Play app signing > Change key: clave propia (PEPK). **Justo después de crear la app y antes del primer AAB** (`references/firma-en-play.md`) | archivo `output.zip` de PEPK; huellas de `app.json` | Sí |
| `first_aab.json` | Testing > Internal testing > Create release: primer AAB | `aab` | No |
| `privacy_policy.json` | App content > Privacy policy | `privacy_url` | No |
| `app_access.json` | App content > App access | `declarations.app_access`, `texts.app_access_instructions` | No |
| `ads.json` | App content > Ads | `declarations.ads` | No |
| `advertising_id.json` | App content > Advertising ID | `declarations.advertising_id` | No |
| `content_rating.json` | App content > Content rating (IARC) | `declarations.content_rating` | Envía el cuestionario |
| `target_audience.json` | App content > Target audience and content | `declarations.target_audience` | No |
| `foreground_services.json` | App content > Foreground service permissions | `declarations.foreground_services`, `texts.fgs_<tipo>`, `videos.fgs_<tipo>` | No |
| `other_declarations.json` | News, Government, Financial features, Health | `declarations.news_app` … `health_apps` | No |
| `category.json` | Store presence > Store settings: categoría, etiquetas | `category`, `tags` | No |
| `countries.json` | Testing / Production > Countries/regions | `countries` | No |
| `closed_test_count.json` | Closed testing: inscritos y días (solo lectura) | — | No |
| `send_for_review.json` | Publishing overview > Send changes for review | — | **Sí: solo con aprobación válida** |
| `production_request.json` | Apply for production (cuestionario de la prueba) | `texts.production_answers` | **Sí** |

Lo demás va por API (`play.py`): ficha, imágenes, contacto (`details`), seguridad de los datos (`data-safety`), testers, versiones, estado de revisión, reseñas.

## Formato

```json
{
  "id": "ads",
  "title": "App content > Ads",
  "status": "draft",
  "verified_at": null,
  "steps": [
    {"do": "goto", "path": "/u/0/developers/${developer}/app/${app_id}/app-content/<ruta grabada>"},
    {"do": "expect", "role": "heading", "name": "<título grabado>"},
    {"do": "when", "value": "${declarations.ads.value}", "equals": false, "steps": [
      {"do": "check", "role": "radio", "name": "<nombre grabado de la opción No>"}
    ]},
    {"do": "save", "role": "button", "name": "Save", "saved_text": "<texto grabado de confirmación>"},
    {"do": "readback", "role": "radio", "name": "<nombre grabado de la opción No>", "checked": true}
  ]
}
```

Pasos: `goto`, `expect`, `click` (con `"commits": true` no se pulsa en ensayo), `check`, `fill` (escribe a ritmo humano), `select`, `upload` (selector de archivos), `save` (no se pulsa en ensayo), `readback` (falla si lo guardado difiere de lo aprobado), `when` y `each` (`${item}`). `${…}` sale del expediente; si falta un valor, la corrida se detiene antes de tocar nada.

## Contenido de la app: lo que se vio en la consola (es-419, 2026-11-15, Keyboard & Mouse)

Página `app/<id>/app-content/overview`. Cada tarjeta tiene el botón **"Comenzar la declaración de <nombre>"** (o "Editar declaración" si quedó en borrador). Al guardar aparece "¿Ir a Descripción general de la publicación?" → *Ahora no*. Nada se envía a revisión hasta *Publishing overview*.

| Declaración | Ruta | Controles (texto exacto) |
|---|---|---|
| Política de Privacidad | `app-content/privacy-policy` | textbox "URL de la política de privacidad" → Guardar |
| Anuncios | `app-content/ads-declaration` | radio "No, mi app no contiene anuncios" → Guardar |
| Detalles de acceso (antes "Acceso a la app") | `app-content/testing-credentials` | "¿Alguna parte de tu app está restringida?" radio "Sí"/"No". "Acciones en otro dispositivo" del Sí se refiere a accesos bloqueados, no a usar la app con otro equipo |
| ID de publicidad | `app-content/ad-id-declaration` | "¿Tu app usa un ID de publicidad?" radio "No"/"Sí" |
| Apps gubernamentales | `app-content/government-apps` | radio "Sí"/"No" |
| Funciones financieras | `app-content/finance` | checkbox "Mi app no ofrece ninguna función financiera" → Siguiente → (Documentación: nada que enviar) → **Guardar** (si no, queda en borrador) |
| Apps de salud | `app-content/health` | checkbox "Ninguna función de salud" → Siguiente → Guardar |
| Clasificación del contenido | `app-content/content-rating-overview` → "Responder el cuestionario" | Paso 1: correo (textbox sin nombre), radio "El resto de los tipos de app", checkbox "Acepto las Condiciones de Uso… IARC" → Siguiente. Paso 2: secciones que se abren solas al responder (9 preguntas Sí/No para una utilidad: contenido descargado, interacción entre usuarios, contenido en línea, productos con restricción de edad, ubicación, compras digitales, recompensas monetarias/NFT, navegador/buscador, noticias/educación) → Guardar → Siguiente. Paso 3: resumen con clasificaciones (utilidad sin nada: "Todas las edades"/ESRB "Todos") → Guardar |
| Público objetivo y contenido | `app-content/target-audience-content` | checkboxes "Menores de 5 años"…"Mayores de 18 años"; con solo 18+ salta al resumen → Guardar |
| Permisos de servicios en primer plano | `app-content/foreground-services` | `connectedDevice` (HID) = checkbox "Transferencia de datos continua a un dispositivo externo" → textbox "Vínculo de video" (Drive/YouTube) → Guardar. No pide descripción |
| Seguridad de los datos | — | por API (`play.py data-safety`); desaparece de la lista |

La encuesta "Ayúdanos a mejorar Play Console" (iframe `google-hats-survey`) tapa los botones: `console.py` la quita sola.
