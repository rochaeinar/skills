# Configuración desde cero (otra PC u otra cuenta)

Este skill no usa cuentas ni claves: todo se genera en la PC.

| Requisito | Para qué | Instalar | Comprobar |
|---|---|---|---|
| Python 3.10+ con Pillow | Recortar capturas, aislar el logo, guardar el PNG final | python.org; `pip install pillow` | `python -c "import PIL"` |
| Microsoft Edge o Google Chrome | Renderizar la plantilla HTML a 1024×500 | Edge viene con Windows | El script lo busca solo; si no lo encuentra, poner su ruta en `"browser"` del config |
| Internet | Las fuentes de Google Fonts de la plantilla | — | — |

## Lo que hay que reunir de la app

- **Capturas reales** del teléfono, en el idioma de la ficha (p. ej. `adb exec-out screencap -p > captura.png`), con datos realistas y sin notificaciones.
- **Logo** (Android: `app/src/main/ic_launcher-playstore.png`) y la **paleta** (`res/values-night/colors.xml`).
- Las **3 funciones** que más venden, la novedad primero.

## Probar

```
python -I "%USERPROFILE%\.claude\skills\play-feature-graphic\scripts\build_feature_graphic.py" <config.json>
```

Debe escribir `feature-graphic-<locale>.png` de 1024×500. Subirla en Play Console → **Presencia en Play Store → Ficha principal → Gráficos → Gráfico de funciones**, una por idioma.
