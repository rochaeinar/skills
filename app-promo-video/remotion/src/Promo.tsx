import { AbsoluteFill } from "remotion";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Background } from "./components/Background";
import { Captions } from "./components/Captions";
import { Soundtrack } from "./components/Soundtrack";
import { Hook } from "./scenes/Hook";
import { Feature } from "./scenes/Feature";
import { Outro } from "./scenes/Outro";
import type { PromoProps, Scene } from "./types";

// Transitions overlap the scenes, so the total is shorter than their sum.
export const promoDuration = (p: PromoProps) =>
  p.scenes.reduce((sum, s) => sum + s.frames, 0) - Math.max(0, p.scenes.length - 1) * p.transitionFrames;

const renderScene = (scene: Scene, props: PromoProps) => {
  switch (scene.type) {
    case "hook":
      return <Hook scene={scene} theme={props.theme} />;
    case "feature":
      return <Feature scene={scene} theme={props.theme} />;
    case "outro":
      return (
        <Outro
          scene={scene}
          theme={props.theme}
          appName={props.appName}
          logo={props.logo}
          logoIncludesName={props.logoIncludesName}
          logoParts={props.logoParts}
        />
      );
  }
};

export const Promo: React.FC<PromoProps> = (props) => (
  <AbsoluteFill style={{ backgroundColor: props.theme.bg }}>
    <Background theme={props.theme} />
    <TransitionSeries>
      {props.scenes.flatMap((scene, i) => {
        const items = [
          <TransitionSeries.Sequence key={`s${i}`} durationInFrames={scene.frames}>
            {renderScene(scene, props)}
          </TransitionSeries.Sequence>,
        ];
        if (i < props.scenes.length - 1) {
          items.push(
            <TransitionSeries.Transition
              key={`t${i}`}
              presentation={fade()}
              timing={springTiming({ config: { damping: 200 }, durationInFrames: props.transitionFrames })}
            />,
          );
        }
        return items;
      })}
    </TransitionSeries>
    <Captions captions={props.captions ?? []} theme={props.theme} />
    <Soundtrack voice={props.voice ?? []} sfx={props.sfx ?? []} music={props.music ?? null} total={promoDuration(props)} />
  </AbsoluteFill>
);
