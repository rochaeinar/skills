import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { Theme } from "../types";

export const alpha = (hex: string, a: number) => `${hex}${Math.round(a * 255).toString(16).padStart(2, "0")}`;

// Brand background: the app's dark color with two soft glows that drift slowly.
export const Background: React.FC<{ theme: Theme }> = ({ theme }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = frame / durationInFrames;
  const x1 = 70 + Math.sin(t * Math.PI * 2) * 12;
  const y1 = 62 + Math.cos(t * Math.PI * 2) * 8;
  return (
    <AbsoluteFill
      style={{
        background: [
          `radial-gradient(circle at ${x1}% ${y1}%, ${alpha(theme.accent, 0.22)}, transparent 48%)`,
          `radial-gradient(circle at ${100 - x1}% 8%, ${alpha(theme.deep, 0.45)}, transparent 52%)`,
          theme.bg,
        ].join(","),
      }}
    />
  );
};
