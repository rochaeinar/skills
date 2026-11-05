<!--
PLANTILLA · Política de privacidad (español). Leer antes references/app-integration.md.
Archivo final: <app>/app/src/main/assets/legal/privacy_es.md.
- Cada frase tiene que ser VERDAD para esta app y estar verificada en su código (manifiesto,
  dependencias de Gradle, llamadas de red, almacenamiento, reglas de respaldo, SDK que arrancan).
  Una sección solo queda si aplica; se reescribe con las funciones reales, nunca se copia el ejemplo.
- Reemplazar cada {{MARCADOR}} y borrar todos los comentarios como este.
  `web.py legal <slug>` rechaza un documento que todavía tenga "{{" o "<!--".
- Misma estructura y numeración en todos los idiomas; español neutro y natural, tuteo.
- No es asesoría legal: el usuario revisa el texto final.
-->
**{{APP}}** · {{DEVELOPER}}  
*Última actualización: {{UPDATED_ES}}*

<!-- Una o dos frases: quién hizo la app, para qué sirve, gratis o de pago, "se ofrece tal como está". -->
{{DEVELOPER}} creó **{{APP}}** como {{ONE_LINE_PURPOSE_ES}}. El servicio se ofrece tal como está.

Esta política explica qué información usa la app, para qué y cómo se protege.

---

## 1. Información que recopilamos

<!-- Elegir UNA apertura que sea verdad:
  A) Sin datos personales y sin internet (sin permiso INTERNET en el manifiesto final):
     "La app **no recopila datos personales** y no se conecta a internet: nada de lo que haces en
     ella se nos envía a nosotros ni a nadie más."
  B) Solo datos técnicos que no identifican (informes de fallos, uso básico, país aproximado…):
     cada uno en negrita, qué es y para qué.
  C) Cuenta, inicio de sesión o contenido del usuario en un servidor: exactamente qué campos, dónde
     se guardan y por cuánto tiempo.
  Después: qué se guarda EN el dispositivo, concreto ("las computadoras que vinculaste, tus macros
  y tus ajustes"). Nombrar el contenido sensible cuando corresponda ("lo que escribes nunca se
  guarda ni se registra"). Registros de diagnóstico locales: si existen y qué nunca contienen. -->

## 2. Permisos

<!-- Una fila por permiso en tiempo de ejecución o sensible del manifiesto FINAL (fusionado):
  el nombre que ve el usuario en Android ("Dispositivos cercanos", "Notificaciones"…) y el motivo
  concreto en esta app. Decir para qué NO se usa cuando pueda preocupar (la búsqueda Bluetooth nunca
  se usa para la ubicación). Los permisos quitados a librerías (tools:node="remove") solo si dan
  confianza ("la app no pide acceso a internet"). -->

| Permiso | Para qué lo usa la app |
| --- | --- |
| {{PERMISO}} | {{MOTIVO}} |

## 3. Servicios de terceros

<!-- Todo SDK que hable con un servidor o reciba datos: Firebase (Crashlytics, Analytics), Google
  Play services, AdMob, facturación, mapas, CDN, APIs de sincronización, geolocalización por IP…
  Buscarlos en las dependencias (`web.py licenses <slug>` las lista), en el código (URLs, clientes
  de API) y en google-services.json. De cada uno: para qué se usa y qué recibe.
  Si no hay ninguno, reemplazar la tabla por: "La app **no usa servicios de terceros**: ni
  analítica, ni publicidad, ni informes de fallos." Decir claramente si muestra anuncios y si algún
  servicio perfila al usuario con fines publicitarios. -->

| Servicio | Para qué se usa |
| --- | --- |
| **{{SERVICIO}}** | {{USO}} |

## 4. Cómo usamos la información

<!-- Solo los fines reales, en una lista corta (que la app funcione, corregir problemas, elegir el
  contenido del idioma…). Después lo negativo: "No la usamos para identificarte, para seguirte en
  otros servicios ni para mostrarte anuncios." -->

## 5. Almacenamiento y seguridad

<!-- Dónde viven los datos: almacenamiento privado de la app en el dispositivo, la cuenta en la nube
  del propio usuario, nuestro servidor. Respaldo de Android: leer android:allowBackup,
  fullBackupContent y dataExtractionRules; decir qué entra en la copia de Google del usuario y qué
  queda fuera (p. ej. los registros).
  Red: "Las conexiones están cifradas (HTTPS)" solo si todos los puntos son HTTPS; sin red, decir
  que nada sale del teléfono salvo <el canal real de la app, p. ej. las teclas por Bluetooth a la
  computadora que conectaste>. -->

## 6. Datos compartidos

<!-- "No vendemos ni compartimos tu información." más toda excepción real (los terceros de arriba,
  obligaciones legales). Apps sin servidor: "Nunca recibimos tu información, así que no podemos
  compartirla." -->

## 7. Control y eliminación de tus datos

<!-- Cómo borra el usuario cada tipo de dato: acciones de la app (borrar una macro, olvidar un
  equipo, cerrar sesión), borrar los datos de la app, desinstalarla, borrar los archivos de su
  propia nube, y cómo pedirnos borrar datos del servidor si los hubiera. -->

## 8. Niños

<!-- Público objetivo según la declaración de Play Console (preguntar al usuario si no se sabe).
  Habitual: "{{APP}} no está dirigida a menores de 13 años y no recopila a sabiendas información de
  ellos." Debe coincidir con la edad de los Términos. -->

## 9. Cambios en esta política

Podemos actualizar esta política. Cada cambio se publica aquí con su nueva fecha de actualización; te recomendamos revisarla de vez en cuando.

## 10. Contacto

Si tienes preguntas sobre esta política, escríbenos a través de nuestro sitio web:

**[{{WEB}}]({{WEB_URL}})**
