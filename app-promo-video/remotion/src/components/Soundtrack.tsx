import { Easing, Html5Audio, Sequence, interpolate, staticFile } from "remotion";
import type { Music, Sfx, VoiceTrack } from "../types";

const DUCK_RAMP = 8; // frames for the music to go down before the voice and back up after it

// The music volume at a frame: lower while a voice speaks, with short ramps around it.
const musicVolume = (frame: number, music: Music, voice: VoiceTrack[], total: number) => {
  let duck = 0;
  for (const v of voice) {
    const d = interpolate(frame, [v.from - DUCK_RAMP, v.from, v.from + v.frames, v.from + v.frames + DUCK_RAMP], [0, 1, 1, 0], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
    duck = Math.max(duck, d);
  }
  // The music is composed to end on the logo; this soft 1.5 s fade (ease-out) is only a safety net.
  const fade = interpolate(frame, [0, 10, total - 45, total], [0, 1, 1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.sin),
  });
  return (music.volume + (music.ducked - music.volume) * duck) * fade;
};

export const Soundtrack: React.FC<{ voice: VoiceTrack[]; sfx: Sfx[]; music: Music | null; total: number }> = ({ voice, sfx, music, total }) => (
  <>
    {music ? <Html5Audio src={staticFile(music.src)} volume={(f) => musicVolume(f, music, voice, total)} /> : null}
    {voice.map((v, i) => (
      <Sequence key={`v${i}`} from={v.from} durationInFrames={v.frames} layout="none">
        <Html5Audio src={staticFile(v.src)} />
      </Sequence>
    ))}
    {sfx.map((s, i) => (
      <Sequence key={`x${i}`} from={s.from} durationInFrames={30} layout="none">
        <Html5Audio src={staticFile(s.src)} volume={s.volume} />
      </Sequence>
    ))}
  </>
);
