// Links between the sites of the monorepo, from site.json (written by web.py link / web.py video).

interface Parent { slug: string; name: string; url: string; locales: string[]; default_locale: string }
interface SiteJson { default_locale: string; youtube?: Record<string, string>; youtube_vertical?: boolean; parent?: Parent | null }

/** The promo video of a page: site.json youtube.<lang>, else the default language's (web.py video). */
export function promoVideo(site: SiteJson, lang: string): { id: string; vertical: boolean } | undefined {
  const all = site.youtube ?? {};
  const id = all[lang] ?? all[site.default_locale];
  return id ? { id, vertical: Boolean(site.youtube_vertical) } : undefined;
}

/** A page of another site in a language it has, else its default language: siteHref(url, locales, "en", "es"). */
export function siteHref(url: string, locales: string[], defaultLocale: string, lang: string): string {
  const base = url.endsWith("/") ? url : `${url}/`;
  return lang !== defaultLocale && locales.includes(lang) ? `${base}${lang}/` : base;
}

/** The main site of the domain (site.json parent), in the page language when it has it. */
export function parentHref(parent: Parent, lang: string): string {
  return siteHref(parent.url, parent.locales, parent.default_locale, lang);
}
