# {{APP}} — Contenido de la app en Google Play

Datos para **Play Console › Política › Contenido de la app** y para los **detalles de contacto** de la ficha. Lo crea el skill `cloudflare-site` con la web de la app; el skill `play-console` lo usa en el primer lanzamiento. Todo sale del análisis de la app (`sites/{{SLUG}}/content/analysis.md` del monorepo de webs), verificado en su código.

## Enlaces

<!-- web.py:links -->
<!-- /web.py:links -->

## Seguridad de los datos

| Pregunta de Play Console | Respuesta | Evidencia en la app |
| --- | --- | --- |
| ¿La app recopila o comparte alguno de los tipos de datos del usuario requeridos? | {{SI_NO}} | {{EVIDENCIA}} |
| ¿Todos los datos del usuario recopilados se encriptan en tránsito? | {{SI_NO_NA}} | {{EVIDENCIA}} |
| ¿Ofreces una forma de que los usuarios soliciten que se borren sus datos? | {{SI_NO_NA}} | {{EVIDENCIA}} |
| Tipos de datos recopilados (y si se comparten, son opcionales, para qué) | {{TIPOS}} | {{EVIDENCIA}} |

## Otras declaraciones

| Sección | Respuesta | Nota |
| --- | --- | --- |
| Anuncios | {{CONTIENE_ANUNCIOS}} | {{EVIDENCIA}} |
| Acceso a la app (cuenta o credenciales para revisar) | {{ACCESO}} | |
| Público objetivo y contenido (edad) | {{EDAD}} | La misma edad que dicen la Política de privacidad y los Términos |
| Permisos y servicios en primer plano a declarar | {{PERMISOS_DECLARAR}} | {{TEXTO_Y_VIDEO}} |
