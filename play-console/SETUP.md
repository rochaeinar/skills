# Configuración desde cero (otra PC u otra cuenta de desarrollador)

Una vez por PC (paso 1) y una vez por **cuenta de desarrollador de Play Console** (pasos 2 a 4). Cada cuenta es un **perfil** con su propia cuenta de servicio. Nombres de la interfaz en español / inglés.

## 1. La PC

| Requisito | Instalar | Comprobar |
|---|---|---|
| Python 3.10+ | python.org | `python --version` |
| Pillow | `python -m pip install --user pillow` | `python -c "import PIL"` |
| cryptography (firma el token de la cuenta de servicio) | `python -m pip install --user cryptography` | `python -c "import cryptography"` |

Ejecutar los comandos con `python` (sin `-I`, que ignora los paquetes del usuario).

## 2. Proyecto de Google Cloud y cuenta de servicio

Con la cuenta de Google **dueña de la cuenta de desarrollador** (o con permisos de administrador en ella):

1. **console.cloud.google.com** → un proyecto (puede ser el mismo de YouTube de esa cuenta) o **Proyecto nuevo / New project**.
2. ☰ → **APIs y servicios / APIs & Services → Biblioteca / Library** → **Google Play Android Developer API** → **Habilitar / Enable**.
3. ☰ → **IAM y administración / IAM & Admin → Cuentas de servicio / Service accounts** → **Crear cuenta de servicio / Create service account**:
   - Nombre: `play-publisher`. **No** hace falta darle roles de Google Cloud (los permisos se dan en Play Console) → **Listo / Done**.
4. Abrir la cuenta de servicio → **Claves / Keys → Agregar clave / Add key → Crear clave nueva / Create new key → JSON** → se descarga un archivo. **Es una contraseña:** no subirlo a ningún repo ni pegarlo en el chat.
   - Si la organización lo impide ("Service account key creation is disabled"), es una política de la organización: crear el proyecto fuera de ella o pedir al administrador que lo permita.
5. Copiar el **correo de la cuenta de servicio** (`play-publisher@<proyecto>.iam.gserviceaccount.com`). Está en cualquiera de estos lugares:
   - Google Cloud → ☰ → **IAM y administración / IAM & Admin → Cuentas de servicio / Service accounts**: columna **Correo electrónico / Email** (al pasar el mouse aparece el ícono para copiarlo).
   - En el JSON descargado: el valor de `"client_email"`.
   - El mensaje final de `play.py auth` (paso 4) lo muestra: `OK: profile '<perfil>' = <correo>`.
   El orden de los pasos 3 y 4 da igual: se puede guardar la clave primero e invitar después.

## 3. Darle acceso en Play Console

Sin esto, todo comando da **HTTP 403 "The caller does not have permission"**.

1. **play.google.com/console** con la cuenta de desarrollador (dueño o administrador).
2. Menú de la izquierda (nivel de la cuenta, no dentro de una app) → **Usuarios y permisos / Users and permissions**.
3. **Invitar usuarios nuevos / Invite new users**.
4. **Dirección de correo / Email address:** el correo de la cuenta de servicio (paso 2.5).
5. Pestaña **Permisos de la app / App permissions** → **Agregar app / Add app** → elegir la app (o varias) → **Aplicar / Apply**, y marcar:
   - **Ver información de la app (solo lectura) / View app information (read-only)**.
   - **Administrar la presencia en Play Store / Manage store presence** (textos, imágenes, video).
   - **Publicar en pistas de prueba / Release to testing tracks** (prueba interna, cerrada y abierta).
   - Solo si se publicará a producción desde el skill: **Publicar en producción / Release to production, exclude devices, and use Play App Signing**.
   - No hace falta ningún permiso de la pestaña **Permisos de la cuenta / Account permissions**.
6. **Invitar usuario / Invite user** → confirmar. La cuenta de servicio no tiene que aceptar nada: queda activa sola.
7. Puede tardar **unos minutos (a veces horas)** en funcionar. Comprobarlo con `play.py status` (paso 5): mientras dé 403, esperar y reintentar.

Para dar acceso a otra app de la misma cuenta más adelante: **Usuarios y permisos** → la cuenta de servicio → **Permisos de la app / App permissions** → **Agregar app**.

## 4. Guardar la clave en el skill (una vez por PC y cuenta)

```
python "%USERPROFILE%\.claude\skills\play-console\scripts\play.py" auth "<ruta>\clave.json" --profile <perfil>
```

- Comprueba la clave contra Google y la guarda en el **Administrador de credenciales de Windows** como `PlayConsole@<perfil>` (cifrada por Windows, solo legible por tu usuario), junto a las demás claves. Guarda solo lo necesario (correo, clave privada y dirección del token, ~1,9 KB en UTF-8), por el límite de 2.560 bytes de cada credencial.
- **Después, borrar el JSON descargado.** Si se pierde la PC o se filtra, revocar la clave en Google Cloud (Cuentas de servicio → Claves → borrar) y crear otra.

## 5. Registrar cada app

```
python "%USERPROFILE%\.claude\skills\play-console\scripts\play.py" register "D:\Documents\<App>\play" --package <applicationId> --profile <perfil>
python "%USERPROFILE%\.claude\skills\play-console\scripts\play.py" status --app "D:\Documents\<App>\play"
python "%USERPROFILE%\.claude\skills\play-console\scripts\play.py" pull --app "D:\Documents\<App>\play" --images
```

`status` debe listar los idiomas y las versiones de cada pista. Si da 403, falta el paso 3 o todavía no se activó. Si da 404, la app no existe en esa cuenta o no tiene su primera versión (ver "Primer lanzamiento" en SKILL.md).

## Varias cuentas de desarrollador

Repetir 2 a 4 con cada cuenta, cada una con su nombre de perfil (`--profile timeless`, `--profile otrodev`). Cada app guarda su perfil en su `play.json`, así que nunca se publica con la cuenta equivocada.
