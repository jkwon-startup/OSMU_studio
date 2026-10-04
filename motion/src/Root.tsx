import { Composition } from "remotion";
import { Scene, SceneProps, defaultSceneProps } from "./Scene";

// build.py 가 --props 로 {template, props, colors, durationInFrames} 를 넘긴다.
// calculateMetadata 로 길이를 props 에서 받는다 (샷마다 길이가 다르므로).
export const Root = () => (
  <Composition
    id="Scene"
    component={Scene}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={90}
    defaultProps={defaultSceneProps}
    calculateMetadata={async ({ props }) => ({
      durationInFrames: Math.max(2, Math.round((props as SceneProps).durationInFrames ?? 90)),
    })}
  />
);
