import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Theme } from "../types";

const bare = (w: string) => w.toLowerCase().replace(/[¿?¡!.,:;«»"]/g, "");

// Words rise in one after another; the words of `keyword` take the accent color.
export const KineticText: React.FC<{
  text: string;
  keyword?: string;
  theme: Theme;
  font: string;
  size: number;
  delay?: number;
  stagger?: number;
  weight?: number;
}> = ({ text, keyword, theme, font, size, delay = 0, stagger = 3, weight = 800 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // The keyword is matched as a phrase (its words in a row), so a short word of it ("y", "a") does
  // not light up the same word elsewhere in the text ("¿Y si...").
  const words = text.split(" ");
  const keyWords = (keyword ?? "").split(" ").filter(Boolean).map(bare);
  const lit = new Set<number>();
  if (keyWords.length) {
    for (let i = 0; i + keyWords.length <= words.length; i++) {
      if (keyWords.every((k, j) => bare(words[i + j]) === k)) keyWords.forEach((_, j) => lit.add(i + j));
    }
  }
  return (
    <div
      style={{
        display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `0 ${size * 0.26}px`,
        fontFamily: font, fontWeight: weight, fontSize: size, lineHeight: 1.12, textAlign: "center", letterSpacing: -0.5,
      }}
    >
      {words.map((word, i) => {
        const s = spring({ frame: frame - delay - i * stagger, fps, config: { damping: 14, stiffness: 140 } });
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              color: lit.has(i) ? theme.accent : theme.text,
              opacity: s,
              transform: `translateY(${interpolate(s, [0, 1], [size * 0.6, 0])}px) scale(${interpolate(s, [0, 1], [0.92, 1])})`,
              textShadow: "0 4px 24px rgba(0,0,0,0.45)",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
