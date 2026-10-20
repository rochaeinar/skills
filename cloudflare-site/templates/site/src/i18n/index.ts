import site from "../../site.json";
import en from "./en.json";

/** The English texts define the shape; every other language is src/i18n/<lang>.json with the same keys. */
export type Texts = typeof en;
const files = import.meta.glob<{ default: Texts }>("./*.json", { eager: true });
const texts: Record<string, Texts> = Object.fromEntries(
  Object.entries(files).map(([path, mod]) => [path.slice(2, -5), mod.default]),
);

export const locales: string[] = site.locales;
export const defaultLocale: string = site.default_locale;
/** Languages written right to left (their pages get dir="rtl"). */
export const rtl = new Set(["ar", "fa", "he", "ur"]);
export const t = (lang: string): Texts => texts[lang] ?? texts[defaultLocale];
/** A path of this site in a language: localePath("es", "/privacy/") -> "/es/privacy/". */
export const localePath = (lang: string, path = "/") => (lang === defaultLocale ? "" : `/${lang}`) + path;
/** getStaticPaths for pages under src/pages/[lang]/: every language but the default one. */
export const otherLocales = () => locales.filter((l) => l !== defaultLocale).map((lang) => ({ params: { lang } }));
/** What LangSuggest shows to speakers of each language. */
export const suggestions = Object.fromEntries(locales.map((l) => [l, t(l).langSuggest]));
export { site };
