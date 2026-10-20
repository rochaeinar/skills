import { AbsoluteFill, useVideoConfig } from "remotion";
import { KineticText } from "../components/KineticText";
import { Phone } from "../components/Phone";
import { body } from "../fonts";
import type { FeatureScene, Theme } from "../types";

// A feature: its title at the top (inside the safe zone) and the phone showing it below.
export const Feature: React.FC<{ scene: FeatureScene; theme: Theme }> = ({ scene, theme }) => {
  const { width, height } = useVideoConfig();
  const vertical = height > width;
  // Horizontal: two columns, the title (and the captions under it) on the left, a bigger phone on the right.
  const phoneW = vertical ? width * 0.66 : height * 0.47;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: vertical ? height * 0.085 : height * 0.3,
          left: vertical ? width * 0.08 : width * 0.07,
          width: vertical ? width * 0.84 : width * 0.46,
        }}
      >
        <KineticText text={scene.text} keyword={scene.keyword} theme={theme} font={body} size={vertical ? 78 : 92} />
      </div>
      <div style={{ position: "absolute", top: vertical ? height * 0.235 : height * 0.035, left: vertical ? (width - phoneW) / 2 : width * 0.6 }}>
        <Phone clip={scene.clip} clipFrom={scene.clipFrom} clipTo={scene.clipTo} rate={scene.rate} width={phoneW} theme={theme} enterDelay={2} />
      </div>
    </AbsoluteFill>
  );
};
