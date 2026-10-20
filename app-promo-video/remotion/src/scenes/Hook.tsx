import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { KineticText } from "../components/KineticText";
import { body } from "../fonts";
import type { HookScene, Theme } from "../types";

// The first seconds: a big question over an AI scene that fills the screen, slowly zooming.
// The scene can still be a placeholder image (before paying for the video): a small tag says so,
// so it is never published by mistake. Without any scene, the question alone on the brand background.
export const Hook: React.FC<{ scene: HookScene; theme: Theme }> = ({ scene, theme }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const vertical = height > width;
  const textScale = interpolate(frame, [0, scene.frames], [1, 1.04]);
  const zoom = interpolate(frame, [0, scene.frames], [1.0, 1.09]);
  const isImage = Boolean(scene.broll && /\.(jpe?g|png|webp)$/i.test(scene.broll));
  const media = { width: "100%", height: "100%", objectFit: "cover" as const, transform: `scale(${zoom})` };
  return (
    <AbsoluteFill>
      {scene.broll ? (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          {isImage ? <Img src={staticFile(scene.broll)} style={media} /> : <OffthreadVideo src={staticFile(scene.broll)} muted style={media} />}
          {/* Dark at the top for the question, a little at the bottom for the cut to the app. */}
          <AbsoluteFill
            style={{
              background: `linear-gradient(180deg, ${theme.bg}E6 0%, ${theme.bg}99 22%, ${theme.bg}1A 45%, ${theme.bg}1A 72%, ${theme.bg}99 100%)`,
            }}
          />
        </AbsoluteFill>
      ) : null}
      <div
        style={{
          // Just below the top safe zone of TikTok (~8%).
          position: "absolute", top: vertical ? height * 0.08 : height * 0.12, left: width * 0.07, width: width * 0.86,
          transform: `scale(${textScale})`,
        }}
      >
        <KineticText text={scene.text} keyword={scene.keyword} theme={theme} font={body} size={vertical ? 104 : 96} stagger={2} />
      </div>
      {scene.brollStage === "placeholder" ? (
        <div
          style={{
            position: "absolute", left: 24, bottom: 24, padding: "8px 16px", borderRadius: 999,
            background: "rgba(0,0,0,0.55)", color: "#FFD54A", fontFamily: body, fontWeight: 700, fontSize: 26,
          }}
        >
          IMAGEN TEMPORAL
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
