import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadCormorant } from "@remotion/google-fonts/CormorantGaramond";

export const body = loadInter("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin", "latin-ext"] }).fontFamily;
export const title = loadCormorant("normal", { weights: ["600", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;
