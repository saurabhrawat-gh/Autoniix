import React from "react";
import { Audio } from "remotion";
import { dbToLinear } from "../../utils/audio";

export interface VoiceoverTrackProps {
  src: string;
  volumeDb?: number;
}

export const VoiceoverTrack: React.FC<VoiceoverTrackProps> = ({ src, volumeDb = 0 }) => {
  return <Audio src={src} volume={dbToLinear(volumeDb)} />;
};
