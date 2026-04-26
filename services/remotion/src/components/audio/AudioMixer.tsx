import React, { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { parseSrt, type SrtCue } from "../../utils/srtParser";
import { VoiceoverTrack } from "./VoiceoverTrack";
import { BackgroundMusic } from "./BackgroundMusic";

export interface AudioMixerProps {
  voiceoverUrl?: string;
  voiceoverSrtUrl?: string;
  /** Inline SRT, takes precedence over srt URL. */
  voiceoverSrt?: string;
  musicUrl?: string;
  musicVolumeDb?: number;
  voiceoverVolumeDb?: number;
  ducking?: {
    enabled: boolean;
    duckingDb?: number; // default -12
    fadeFrames?: number; // default 6
  };
}

/**
 * Orchestrates all global audio tracks for the composition:
 *  1. Voiceover (full volume unless user overrides)
 *  2. Background music (base volume + optional smart ducking under VO)
 *
 * If `ducking.enabled` and an SRT is provided, the music volume drops by
 * `duckingDb` dB during spoken cues with attack/release fades of `fadeFrames`.
 */
export const AudioMixer: React.FC<AudioMixerProps> = ({
  voiceoverUrl,
  voiceoverSrtUrl,
  voiceoverSrt,
  musicUrl,
  musicVolumeDb = -18,
  voiceoverVolumeDb = 0,
  ducking = { enabled: true, duckingDb: -12, fadeFrames: 6 },
}) => {
  const [cues, setCues] = useState<SrtCue[] | null>(null);

  useEffect(() => {
    if (voiceoverSrt) {
      setCues(parseSrt(voiceoverSrt));
      return;
    }
    if (!voiceoverSrtUrl || !ducking.enabled) {
      setCues([]);
      return;
    }
    const handle = delayRender(`fetch-vo-srt:${voiceoverSrtUrl}`);
    fetch(voiceoverSrtUrl)
      .then((r) => r.text())
      .then((txt) => {
        setCues(parseSrt(txt));
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
  }, [voiceoverSrtUrl, voiceoverSrt, ducking.enabled]);

  // Wait for SRT (if requested) before rendering the music track so ducking is correct.
  if (ducking.enabled && (voiceoverSrtUrl || voiceoverSrt) && cues === null) {
    return null;
  }

  return (
    <>
      {voiceoverUrl && <VoiceoverTrack src={voiceoverUrl} volumeDb={voiceoverVolumeDb} />}
      {musicUrl && (
        <BackgroundMusic
          src={musicUrl}
          volumeDb={musicVolumeDb}
          duckCues={ducking.enabled && cues && cues.length > 0 ? cues : undefined}
          duckingDb={ducking.duckingDb ?? -12}
          fadeFrames={ducking.fadeFrames ?? 6}
        />
      )}
    </>
  );
};
