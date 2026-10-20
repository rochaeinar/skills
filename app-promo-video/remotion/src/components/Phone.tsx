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
  width: number;
  theme: Theme;
  enterDelay?: number;
  tiltY?: number;
  enterFrom?: number; // px below its place where it starts rising
};

export const Phone: React.FC<Props> = ({ clip, clipFrom, clipTo, rate = 1, width, theme, enterDelay = 0, tiltY = -16, enterFrom = 420 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const bezel = Math.round(width * 0.024);
  const screenW = width - bezel * 2;
  const statusH = Math.round(screenW * (112 / 1080));
  const screenH = Math.round(screenW / SCREEN_RATIO) + statusH;
  const radius = width * 0.11;

  // Critically damped: it settles without bouncing past straight.
  const enter = spring({ frame: frame - enterDelay, fps, config: { damping: 26, stiffness: 80, mass: 1 } });
  const rotateX = interpolate(enter, [0, 1], [26, 0]);
  const rotateY = interpolate(enter, [0, 1], [tiltY, 0]);
  const translateY = interpolate(enter, [0, 1], [enterFrom, 0]);
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.015]);
  const scale = interpolate(enter, [0, 1], [0.88, 1]) * zoom;

  return (
    <div style={{ perspective: 2400, width, height: screenH + bezel * 2 }}>
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
          <StatusBar width={screenW} height={statusH} theme={theme} font={body} />
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(115deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 32%)" }} />
        </div>
      </div>
    </div>
  );
};
