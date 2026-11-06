import { OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { StatusBar } from "./StatusBar";
import { body } from "../fonts";
import type { Theme } from "../types";

// A phone in 2.5D: it rises with a spring from a tilt and ends perfectly straight (a phone left
// askew looks careless); then it only zooms in a little, so it stays alive without turning.
// The screen shows a recording (cropped of its system bars) under a clean status bar.
export const SCREEN_RATIO = 1080 / 2092; // width / height of the cropped recordings

type Props = {
  clip: string;
  clipFrom: number;
  clipTo: number;
  rate?: number;
  clipRatio?: number; // the recording's width / height; the screen takes it so nothing is cut
  width: number;
  theme: Theme;
  enterDelay?: number;
  tiltY?: number;
  enterFrom?: number; // px below its place where it starts rising
};

export const Phone: React.FC<Props> = ({ clip, clipFrom, clipTo, rate = 1, clipRatio, width: boxW, theme, enterDelay = 0, tiltY = -16, enterFrom = 420 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  // The phone keeps the height of the layout; a recording of another shape (a taller phone) makes
  // the screen narrower instead of cropping it with "cover".
  const bezel = Math.round(boxW * 0.024);
  const boxScreenW = boxW - bezel * 2;
  const statusH = Math.round(boxScreenW * (112 / 1080));
  const screenH = Math.round(boxScreenW / SCREEN_RATIO) + statusH;
  const screenW = clipRatio ? Math.round((screenH - statusH) * clipRatio) : boxScreenW;
  const width = screenW + bezel * 2;
  const radius = width * 0.11;

  // Critically damped: it settles without bouncing past straight.
  const enter = spring({ frame: frame - enterDelay, fps, config: { damping: 26, stiffness: 80, mass: 1 } });
  const rotateX = interpolate(enter, [0, 1], [26, 0]);
  const rotateY = interpolate(enter, [0, 1], [tiltY, 0]);
  const translateY = interpolate(enter, [0, 1], [enterFrom, 0]);
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.015]);
  const scale = interpolate(enter, [0, 1], [0.88, 1]) * zoom;

  return (
    <div style={{ perspective: 2400, width, height: screenH + bezel * 2, marginLeft: (boxW - width) / 2 }}>
      <div
        style={{
          width, height: screenH + bezel * 2, borderRadius: radius, background: "#050708",
          padding: bezel, boxSizing: "border-box", position: "relative",
          transform: `translateY(${translateY}px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${scale})`,
          boxShadow: "0 0 0 3px #2b3437, 0 60px 120px rgba(0,0,0,0.55), 0 20px 40px rgba(0,0,0,0.35)",
        }}
      >
        <div style={{ width: screenW, height: screenH, borderRadius: radius - bezel, overflow: "hidden", position: "relative", background: theme.screenBg }}>
          <OffthreadVideo
            src={staticFile(clip)}
            trimBefore={Math.round(clipFrom * fps)}
            trimAfter={Math.round(clipTo * fps)}
            playbackRate={rate}
            muted
            style={{ position: "absolute", top: statusH, left: 0, width: screenW, height: screenH - statusH, objectFit: "cover" }}
          />
          {/* Behind the clean status bar, the first rows of the recording stretched to its height: an
              app that paints under the status bar (a red REC bar, a colored header) keeps its color
              up to the top, as on the phone, instead of a band of the theme's background. */}
          <div style={{ position: "absolute", top: 0, left: 0, width: screenW, height: statusH, overflow: "hidden" }}>
            <OffthreadVideo
              src={staticFile(clip)}
              trimBefore={Math.round(clipFrom * fps)}
              trimAfter={Math.round(clipTo * fps)}
              playbackRate={rate}
              muted
              style={{ position: "absolute", top: 0, left: 0, width: screenW, height: screenH - statusH,
                       transformOrigin: "top", transform: `scaleY(${statusH / 4})` }}
            />
          </div>
          <StatusBar width={screenW} height={statusH} theme={theme} font={body} background="transparent" />
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(115deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 32%)" }} />
        </div>
      </div>
    </div>
  );
};
