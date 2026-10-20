import site from "../../site.json";
import en from "./en.json";
import es from "./es.json";

export type Texts = typeof en;
const texts: Record<string, Texts> = { en, es };

export const locales: string[] = site.locales;
export const defaultLocale: string = site.default_locale;
export const t = (lang: string): Texts => texts[lang] ?? texts[defaultLocale];
/** A path of this site in a language: localePath("es", "/privacy/") -> "/es/privacy/". */
export const localePath = (lang: string, path = "/") => (lang === defaultLocale ? "" : `/${lang}`) + path;
export { site };
