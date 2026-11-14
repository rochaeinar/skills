# Pantallas de Play Console (las que no tienen API)

Cada pantalla es un archivo `<pantalla>.json` con pasos declarativos que `console.py run` ejecuta sobre el expediente **aprobado**. Ningún archivo trae selectores inventados: **se graban la primera vez (F0)** mirando la pantalla real y quedan en `"status": "draft"` hasta que una corrida en `--dry-run` y una real los validan; entonces pasan a `"verified"` con la fecha.

## Cómo se graba una pantalla (Claude, con el usuario mirando solo la primera vez)

1. `console.py whoami --profile <perfil>` (cuenta correcta).
2. Navegar a la pantalla y `console.py snapshot --profile <perfil> --name <pantalla>`: captura + árbol de accesibilidad (`.aria.yaml`, con roles y nombres exactos).
3. Escribir los pasos con los **roles y nombres del árbol** (nunca clases CSS ni posiciones). Consola en **inglés**.
4. `console.py run <pantalla> --app <carpeta> --dry-run`: llena sin guardar y deja la captura. Revisarla con Read.
5. Corrida real, con `readback` de cada campo. Si pasa: `"status": "verified"`, `"verified_at": "<fecha>"`.
6. Si Google cambia la pantalla, la corrida se detiene con captura y árbol: repetir 2-5 solo en esa pantalla.

## Pantallas necesarias

| Archivo | Pantalla de Play Console | Usa del expediente | Irreversible |
|---|---|---|---|
| `create_app.json` | Home > Create app (nombre, idioma, app/juego, gratis, declaraciones) | `name`, `default_language`, `type`, `free` | Sí (gratis no vuelve a pago) |
| `app_signing.json` | Test and release > App integrity > App signing: clave propia (PEPK) | archivo `output.zip` de PEPK | Sí |
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
