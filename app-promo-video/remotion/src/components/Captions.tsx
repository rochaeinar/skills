import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { body } from "../fonts";
import type { Caption, Theme } from "../types";

// Captions of the voice, a few words at a time, the word being said in the accent color.
// For the many who watch without sound. In the vertical video they sit above the bottom 20%
// (TikTok's description) and away from the right edge (its buttons); in the horizontal one, in the
// left column under the title, so they never cover the phone.
export const Captions: React.FC<{ captions: Caption[]; theme: Theme }> = ({ captions, theme }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;
  const current = captions.find((c) => frame >= c.from && frame < c.to);
  if (!current) return null;
  const pop = spring({ frame: frame - current.from, fps, config: { damping: 16, stiffness: 180 } });
  const out = interpolate(frame, [current.to - 4, current.to], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute", left: vertical ? 0 : width * 0.07, width: vertical ? width : width * 0.46,
        top: vertical ? height * 0.7 : height * 0.66,
        display: "flex", justifyContent: "center", pointerEvents: "none",
        opacity: Math.min(pop, out), transform: `translateY(${interpolate(pop, [0, 1], [18, 0])}px) scale(${interpolate(pop, [0, 1], [0.94, 1])})`,
      }}
    >
      <div
        style={{
          maxWidth: vertical ? width * 0.8 : width * 0.44, padding: vertical ? "18px 30px" : "16px 30px", borderRadius: 26,
          background: "rgba(8, 12, 13, 0.78)", boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
          fontFamily: body, fontWeight: 800, fontSize: vertical ? 56 : 44, lineHeight: 1.15, textAlign: "center",
          display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 0.28em",
        }}
      >
        {current.words.map((w, i) => (
          <span key={i} style={{ color: frame >= w.from ? (frame < w.to ? theme.accent : theme.text) : "rgba(238,243,241,0.55)" }}>
            {w.text}
          </span>
        ))}
      </div>
    </div>
  );
};
