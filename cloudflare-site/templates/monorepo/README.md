# Websites

Sitios estáticos de las apps, uno por subdominio, publicados en **Cloudflare Pages** (Direct Upload con wrangler) en varias cuentas de Cloudflare. Hechos con **Astro** y workspaces de npm.

```
accounts.json        perfil -> Account ID y zonas (sin secretos; los tokens están en el Administrador de credenciales de Windows)
packages/ui/         componentes compartidos: SEO, insignia de Google Play, YouTube, analítica, idioma
sites/<app>/         un sitio por app
  site.json          cuenta (perfil), proyecto de Pages, dominio, idiomas, paquete de Play, carpetas externas
  content/           análisis de la app, inventario de imágenes (no se publica)
  src/               páginas, componentes, textos por idioma (src/i18n), imágenes (src/assets)
  public/            archivos tal cual (_headers, videos, íconos)
```

Todo se maneja con el skill **`cloudflare-site`** de Claude Code (`web.py`): crear un sitio, analizar la app, capturas del teléfono, build con controles, deploy de vista previa o producción, dominio propio, estado.

```
npm install
python "%USERPROFILE%\.claude\skills\cloudflare-site\scripts\web.py" status
python "%USERPROFILE%\.claude\skills\cloudflare-site\scripts\web.py" build <app>
python "%USERPROFILE%\.claude\skills\cloudflare-site\scripts\web.py" deploy <app>                 vista previa
python "%USERPROFILE%\.claude\skills\cloudflare-site\scripts\web.py" deploy <app> --prod --yes     producción
python "%USERPROFILE%\.claude\skills\cloudflare-site\scripts\web.py" deploy --changed --prod --yes solo los que cambiaron
```

Local: `npm run dev -w sites/<app>`.
