# play-launch: preparación (una vez por PC y por cuenta)

## 1. Herramientas de la PC

- Python 3 con Playwright: `python -m pip install --user playwright`. **No** hace falta `playwright install`: los scripts se conectan al navegador del usuario, no descargan ni lanzan otro.
- Pillow (tamaños de imágenes): `python -m pip install --user pillow`.
- Android SDK con `build-tools` (usa `aapt2`). Ya viene con Android Studio.
- Microsoft Edge (viene con Windows) o Google Chrome.
- El skill `play-console` configurado para la cuenta (su `SETUP.md`: cuenta de servicio y `play.py auth`).

## 2. Cuenta de desarrollador (el usuario, a mano)

1. Crear la cuenta de Play Console, pagar y verificar la identidad. Decidir antes **personal u organización** (plan §5).
2. Cuenta de servicio con permisos mínimos para las apps (versiones, ficha, testers): `play-console/SETUP.md`.
3. **Grupo de Google** con los testers (p. ej. `testers-erasoft@googlegroups.com`): se agrega a cada app por API.
4. Un correo público de contacto para las fichas.

## 3. Navegador dedicado

1. `python scripts/console.py open --profile <perfil>` (por defecto Edge; `--browser chrome` si se prefiere). Abre una ventana con un perfil propio en `%LOCALAPPDATA%\play-launch\browser-<perfil>`, separado del navegador de todos los días.
2. **El usuario inicia sesión a mano** con el Google de la cuenta de desarrollador (con 2FA) y abre Play Console.
3. En Play Console: **Settings > Preferences > Language: English** (las pantallas se graban en inglés).
4. `python scripts/console.py bind --profile <perfil>`: guarda el id de la cuenta de desarrollador. Desde entonces, si el navegador tiene otra cuenta abierta, nada se ejecuta.
5. La sesión dura semanas. Cuando venza, `console.py whoami` lo dice y el usuario vuelve a iniciar sesión.

## 4. Pase diario (opcional, sin Claude)

Programador de tareas de Windows, todos los días a las 9:07:

```powershell
$a = New-ScheduledTaskAction -Execute "python" -Argument "`"$env:USERPROFILE\.claude\skills\play-launch\scripts\launch.py`" tick --notify"
$t = New-ScheduledTaskTrigger -Daily -At 9:07am
Register-ScheduledTask -TaskName "play-launch tick" -Action $a -Trigger $t -Description "Estado de las apps en Play (solo API)"
```

Solo usa la API: nunca abre pantallas ni toca la sesión. Muestra un mensaje si algo necesita al usuario.

## 5. Primera app de la cuenta (F0)

Las pantallas sin API se graban la primera vez, con el usuario mirando (`screens/README.md`). Después quedan verificadas y sirven para todas las apps de esa consola, hasta que Google las cambie.

Pendientes que se resuelven en F0:
- Exportar la plantilla del CSV de seguridad de los datos a `templates/data-safety-template.csv`.
- Comprobar que Google acepta la sesión en el navegador dedicado sin pedirla otra vez al conectarse los scripts.
- Dónde alojar el video de los servicios en primer plano para que el revisor lo vea (YouTube oculto subido a mano, o Drive con enlace): un proyecto de API de YouTube sin auditoría deja los videos en privado.
