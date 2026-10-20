# Skills de Claude Code

Copia de seguridad de los skills propios. Claude Code los carga desde `%USERPROFILE%\.claude\skills\` (Windows) o `~/.claude/skills/` (macOS y Linux): esta carpeta es el respaldo y el historial.

| Skill | Qué hace | Configuración |
|---|---|---|
| `play-feature-graphic` | Imagen destacada de Google Play (1024×500) desde capturas reales, en varios idiomas | `play-feature-graphic/SETUP.md` |
| `play-console` | Ficha de Play Store (textos, video, ícono, imagen destacada, capturas) y versiones (AAB, pistas, notas, lanzamiento escalonado) desde archivos, para varias cuentas de desarrollador | `play-console/SETUP.md` |
| `app-promo-video` | Videos promocionales de apps (TikTok, Reels, Shorts, YouTube y Google Play): grabación con Maestro, voz y música con ElevenLabs, gancho con IA (fal.ai), edición con Remotion, control de calidad y subida a YouTube | `app-promo-video/SETUP.md` |

## Instalar en otra PC

1. Copiar cada carpeta de skill a `%USERPROFILE%\.claude\skills\`:
   ```powershell
   Copy-Item -Recurse D:\Projects\skills\app-promo-video, D:\Projects\skills\play-feature-graphic, D:\Projects\skills\play-console "$env:USERPROFILE\.claude\skills\"
   ```
2. Seguir el `SETUP.md` de cada skill (herramientas, cuentas y claves). **Las claves nunca están en esta carpeta**: se crean de nuevo en cada PC, en el Administrador de credenciales de Windows.
3. Abrir una sesión nueva de Claude Code: los skills aparecen en la lista. Para usarlos, pedir por ejemplo "haz un video promocional de mi app" o "genera la imagen destacada de Play".

## Mantener el respaldo al día

Después de cambiar un skill, copiarlo otra vez aquí (sin `remotion/node_modules` ni `__pycache__`, que se regeneran solos) y hacer commit.

## Ejemplo real

Bible Versions (`com.timeless.bible`): configuración en `D:\Documents\BibleVersions\Images\promo-video\video.json` y `...\feature-graphic\feature-graphic.json`; flujos de grabación en `D:\Projects\Android\bible-versions\.maestro\promo\`; historia y decisiones en `plans/promo-video-skill-plan.md` de ese repo.
