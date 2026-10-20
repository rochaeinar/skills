import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import site from "./site.json" with { type: "json" };

// Static output only: every page is HTML built here and served by Cloudflare Pages from its CDN.
export default defineConfig({
  site: `https://${site.domain}`,
  output: "static",
  trailingSlash: "always",
  build: { format: "directory" },
  i18n: {
    locales: site.locales,
    defaultLocale: site.default_locale,
    routing: { prefixDefaultLocale: false },
  },
  integrations: [
    sitemap({ i18n: { defaultLocale: site.default_locale, locales: Object.fromEntries(site.locales.map((l) => [l, l])) } }),
  ],
});
