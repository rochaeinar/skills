import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadCormorant } from "@remotion/google-fonts/CormorantGaramond";
import { loadFont as loadNotoSansDeva } from "@remotion/google-fonts/NotoSansDevanagari";
import { loadFont as loadNotoSerifDeva } from "@remotion/google-fonts/NotoSerifDevanagari";

// Inter and Cormorant only have Latin: Devanagari (Hindi) falls back, glyph by glyph, to Noto.
const inter = loadInter("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin", "latin-ext"] }).fontFamily;
const cormorant = loadCormorant("normal", { weights: ["600", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;
const notoSans = loadNotoSansDeva("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["devanagari"] }).fontFamily;
const notoSerif = loadNotoSerifDeva("normal", { weights: ["600", "700"], subsets: ["devanagari"] }).fontFamily;

export const body = `${inter}, ${notoSans}`;
export const title = `${cormorant}, ${notoSerif}`;
