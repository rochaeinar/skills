# Skills de Claude Code

Copia de seguridad de los skills propios. Claude Code los carga desde `%USERPROFILE%\.claude\skills\` (Windows) o `~/.claude/skills/` (macOS y Linux): esta carpeta es el respaldo y el historial.

| Skill | Qué hace | Configuración |
|---|---|---|
| `play-feature-graphic` | Imagen destacada de Google Play (1024×500) desde capturas reales, en varios idiomas | `play-feature-graphic/SETUP.md` |
| `play-console` | Ficha de Play Store (textos, video, ícono, imagen destacada, capturas) y versiones (AAB, pistas, notas, lanzamiento escalonado) desde archivos, para varias cuentas de desarrollador | `play-console/SETUP.md` |
| `android-release` | Versión nueva a Google Play de punta a punta: versión = fecha de hoy y código verificado contra Play, tests, AAB release firmado, notas por idioma y publicación con `play-console` | `android-release/SETUP.md` |
| `cloudflare-site` | Web oficial de cada app (Astro estático, un subdominio por app) en Cloudflare Pages desde un monorepo, con varias cuentas de Cloudflare: análisis de la app, capturas, mockups en Claude Design, controles de calidad y deploy con wrangler | `cloudflare-site/SETUP.md` |
| `app-promo-video` | Videos promocionales de apps (TikTok, Reels, Shorts, YouTube y Google Play): grabación con Maestro, voz y música con ElevenLabs, gancho con IA (fal.ai), edición con Remotion, control de calidad y subida a YouTube | `app-promo-video/SETUP.md` |
| `bible-language-pack` | Idiomas nuevos de Bible Versions, uno a la vez: Biblias descargadas → numeración KJV, validación de calidad (reporte + hoja de revisión humana), paquete `.obb` con la Biblia en el idioma y el resto en inglés, subida a R2 y manifest | `bible-language-pack/SETUP.md` |
| `bible-language-ship` | Del paquete validado a "listo para publicar": CDN y manifiesto, idioma en la app (voz, interfaz, Acerca de con los créditos de los módulos), web (sin deploy), ficha y capturas de Play, test Maestro del texto bíblico; pensado para correr sin parar idioma por idioma | `bible-language-ship/SETUP.md` |
| `bible-devotional-translate` | Reflexión diaria de Bible Versions (`coffee_es.dev`) en otros idiomas: traducción desde el español con el inglés de apoyo, por tandas e incremental (solo filas nuevas o cambiadas), validación, módulo con Id registrado en el paquete del idioma y `languages.json`, y repaquetado del español y el inglés | `bible-devotional-translate/SETUP.md` |

## Instalar en otra PC

1. Copiar cada carpeta de skill a `%USERPROFILE%\.claude\skills\`:
   ```powershell
   Copy-Item -Recurse D:\Projects\skills\app-promo-video, D:\Projects\skills\play-feature-graphic, D:\Projects\skills\play-console, D:\Projects\skills\android-release, D:\Projects\skills\cloudflare-site, D:\Projects\skills\bible-language-pack, D:\Projects\skills\bible-language-ship, D:\Projects\skills\bible-devotional-translate "$env:USERPROFILE\.claude\skills\"
   ```
2. Seguir el `SETUP.md` de cada skill (herramientas, cuentas y claves). **Las claves nunca están en esta carpeta**: se crean de nuevo en cada PC, en el Administrador de credenciales de Windows.
3. Abrir una sesión nueva de Claude Code: los skills aparecen en la lista. Para usarlos, pedir por ejemplo "haz un video promocional de mi app" o "genera la imagen destacada de Play".

## Mantener el respaldo al día

Después de cambiar un skill, copiarlo otra vez aquí (sin `remotion/node_modules` ni `__pycache__`, que se regeneran solos) y hacer commit.

## Ejemplo real

Bible Versions (`com.timeless.bible`): configuración en `D:\Documents\BibleVersions\Images\promo-video\video.json` y `...\feature-graphic\feature-graphic.json`; flujos de grabación en `D:\Projects\Android\bible-versions\.maestro\promo\`; historia y decisiones en `plans/promo-video-skill-plan.md` de ese repo.
