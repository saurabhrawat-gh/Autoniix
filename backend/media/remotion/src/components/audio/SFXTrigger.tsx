import React from "react";
import { Audio, Sequence } from "remotion";
import { dbToLinear } from "../../utils/audio";

export interface SFXTriggerProps {
  src: string;
  /** Frame (in composition timeline) at which the SFX should start. */
  triggerAtFrame: number;
  /** Optional max length of the SFX in frames (auto if omitted). */
  durationInFrames?: number;
  volumeDb?: number;
}

export const SFXTrigger: React.FC<SFXTriggerProps> = ({
  src,
  triggerAtFrame,
  durationInFrames,
  volumeDb = 0,
}) => {
  return (
    <Sequence from={triggerAtFrame} durationInFrames={durationInFrames}>
      <Audio src={src} volume={dbToLinear(volumeDb)} />
    </Sequence>
  );
};
