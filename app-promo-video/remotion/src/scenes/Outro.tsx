import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body, title } from "../fonts";
import type { OutroScene, Theme } from "../types";

const FISH_FRAMES = 27; // as render.py: the swim into the logo

// The close: the logo, the app name (unless the logo has it), the tagline and the call to action.
// With the logo in two layers (logoParts) it plays the app's splash: the school settles in, and
// once the call to action has been said the green fish swims in against the current to its place.
export const Outro: React.FC<{
  scene: OutroScene;
  theme: Theme;
  appName: string;
  logo: string;
  logoIncludesName: boolean;
  logoParts?: { school: string; fish: string } | null;
}> = ({ scene, theme, appName, logo, logoIncludesName, logoParts }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;
  const pop = (delay: number) => spring({ frame: frame - delay, fps, config: { damping: 13, stiffness: 120 } });
  const logoS = pop(0);
  const nameS = pop(6);
  const tagS = pop(10);
  const ctaS = pop(16);
  const pulse = ctaS > 0.98 ? 1 + Math.sin((frame - 30) / 6) * 0.025 : 1;
  const rise = (s: number) => ({ opacity: s, transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)` });
  const logoW = logoIncludesName ? (vertical ? 640 : 440) : vertical ? 300 : 220;
  const logoStyle = { width: logoW, height: logoW, objectFit: "contain" as const, position: "absolute" as const, inset: 0 };

  // The splash of the app (drawable/splash_fish_animated.xml), slower so it can be seen in a video.
  const settle = interpolate(frame, [0, 14], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const fishFrom = scene.fishFrom ?? 45;
  const swim = interpolate(frame, [fishFrom, fishFrom + FISH_FRAMES], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic),
  });
  const shift = (1 - swim) * logoW * 0.2; // starts down and to the left, swims up and right
  const wiggle = Math.sin((frame - fishFrom) / 2.2) * 7 * (1 - swim) * (swim > 0 ? 1 : 0); // tail beats while it swims

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: vertical ? 30 : 20 }}>
      {logoParts ? (
        <div style={{ position: "relative", width: logoW, height: logoW, transform: `scale(${interpolate(logoS, [0, 1], [0.9, 1])})` }}>
          <Img
            src={staticFile(logoParts.school)}
            style={{ ...logoStyle, opacity: interpolate(settle, [0, 1], [0.35, 1]), transform: `translateY(${interpolate(settle, [0, 1], [-logoW * 0.03, 0])}px)` }}
          />
          <Img
            src={staticFile(logoParts.fish)}
            style={{
              ...logoStyle,
              opacity: interpolate(swim, [0, 0.45], [0, 1], { extrapolateRight: "clamp" }),
              transform: `translate(${-shift}px, ${shift}px) rotate(${wiggle}deg)`,
              transformOrigin: "70% 30%",
            }}
          />
        </div>
      ) : (
        <Img
          src={staticFile(logo)}
          style={{ width: logoW, height: logoW, objectFit: "contain", transform: `scale(${logoS}) rotate(${interpolate(logoS, [0, 1], [-10, 0])}deg)` }}
        />
      )}
      {logoIncludesName ? null : (
        <div style={{ ...rise(nameS), fontFamily: title, fontWeight: 700, fontSize: vertical ? 150 : 120, color: theme.text, lineHeight: 0.95, textAlign: "center" }}>
          {appName}
        </div>
      )}
      {scene.tagline ? (
        <div style={{ ...rise(tagS), fontFamily: body, fontWeight: 500, fontSize: vertical ? 46 : 38, color: theme.muted, textAlign: "center", maxWidth: width * 0.8 }}>
          {scene.tagline}
        </div>
      ) : null}
      <div
        style={{
          ...rise(ctaS), marginTop: vertical ? 30 : 16, padding: vertical ? "30px 64px" : "22px 48px", borderRadius: 999,
          background: theme.accent, color: theme.onAccent, fontFamily: body, fontWeight: 800, fontSize: vertical ? 54 : 44,
          boxShadow: `0 20px 60px ${theme.accent}55`, scale: String(pulse),
        }}
      >
        {scene.text}
      </div>
    </AbsoluteFill>
  );
};
