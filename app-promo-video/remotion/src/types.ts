// Props of the Promo composition. scripts/render.py builds them from video.json and the app's
// feature-graphic config; every path is relative to the public dir (the app's promo-video folder).
export type Theme = {
  bg: string;
  accent: string;
  accentSoft: string;
  deep: string;
  text: string;
  muted: string;
  onAccent: string;
  screenBg: string;
};

export type HookScene = {
  type: "hook";
  frames: number;
  text: string;
  keyword?: string;
  clip?: string; // phone rising behind the text, optional
  clipFrom?: number; // seconds
  clipTo?: number;
  broll?: string; // AI scene behind the text: a video, or a still image (placeholder)
  brollStage?: "placeholder" | "draft" | "final";
};

export type FeatureScene = {
  type: "feature";
  frames: number;
  text: string;
  keyword?: string;
  clip: string;
  clipFrom: number; // seconds
  clipTo: number;
  rate: number;
};

export type OutroScene = {
  type: "outro";
  frames: number;
  text: string; // call to action
  tagline?: string;
  fishFrom?: number; // frame of the scene when the green fish swims into the logo (with logoParts)
};

export type Scene = HookScene | FeatureScene | OutroScene;

// Audio and captions use absolute frames of the whole video (render.py computes them).
export type VoiceTrack = { src: string; from: number; frames: number };
export type CaptionWord = { text: string; from: number; to: number };
export type Caption = { from: number; to: number; words: CaptionWord[] };
export type Sfx = { src: string; from: number; volume: number };
export type Music = { src: string; volume: number; ducked: number };

export type PromoProps = {
  width: number;
  height: number;
  fps: number;
  appName: string;
  logo: string;
  logoIncludesName: boolean; // the logo already shows the app name: the outro does not repeat it
  // The logo in two layers of the same size, to animate its fish as the app's splash does.
  logoParts?: { school: string; fish: string } | null;
  theme: Theme;
  transitionFrames: number;
  scenes: Scene[];
  voice: VoiceTrack[];
  captions: Caption[];
  sfx: Sfx[];
  music: Music | null; // null: voice only (a song is picked in TikTok's library instead)
};
