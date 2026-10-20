import { Composition } from "remotion";
import { Promo, promoDuration } from "./Promo";
import type { PromoProps } from "./types";

const defaults: PromoProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  appName: "App",
  logo: "assets/logo.png",
  logoIncludesName: false,
  logoParts: null,
  transitionFrames: 12,
  theme: {
    bg: "#12181A", accent: "#49CC87", accentSoft: "#82BFAB", deep: "#1E6B57",
    text: "#EEF3F1", muted: "#9AA8A4", onAccent: "#0D1F17", screenBg: "#12181A",
  },
  scenes: [{ type: "outro", frames: 90, text: "Get it on Google Play" }],
  voice: [],
  captions: [],
  sfx: [],
  music: null,
};

export const Root: React.FC = () => (
  <Composition
    id="Promo"
    component={Promo}
    defaultProps={defaults}
    width={defaults.width}
    height={defaults.height}
    fps={defaults.fps}
    durationInFrames={promoDuration(defaults)}
    calculateMetadata={({ props }) => ({
      width: props.width,
      height: props.height,
      fps: props.fps,
      durationInFrames: promoDuration(props),
    })}
  />
);
