import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  cancelRender,
  continueRender,
  delayRender,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { parseSrt, wordsFromCues, type SrtCue, type SrtWord } from "../../utils/srtParser";

export type CaptionStyle =
  "word_highlight_yellow" | "subtitle_bottom_center" | "karaoke_colored" | "big_bold_shorts";

export interface CaptionOverlayProps {
  srtUrl?: string;
  /** Inline SRT string (takes precedence over srtUrl). */
  srt?: string;
  style?: CaptionStyle;
  accent?: string;
  maxWords?: number;
}

const BASE_TEXT: React.CSSProperties = {
  fontFamily: "Inter, system-ui, sans-serif",
  fontWeight: 900,
  color: "#fff",
  textAlign: "center",
  lineHeight: 1.1,
  letterSpacing: -0.5,
  textShadow: "0 4px 24px rgba(0,0,0,0.7)",
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  srtUrl,
  srt,
  style = "word_highlight_yellow",
  accent = "#FFD60A",
  maxWords = 6,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [cues, setCues] = useState<SrtCue[]>([]);
  const [words, setWords] = useState<SrtWord[]>([]);

  useEffect(() => {
    if (srt) {
      const c = parseSrt(srt);
      setCues(c);
      setWords(wordsFromCues(c));
      return;
    }
    if (!srtUrl) return;
    const handle = delayRender(`fetch-srt:${srtUrl}`);
    fetch(srtUrl)
      .then((r) => r.text())
      .then((txt) => {
        const c = parseSrt(txt);
        setCues(c);
        setWords(wordsFromCues(c));
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
  }, [srtUrl, srt]);

  const ms = (frame / fps) * 1000;

  let body: React.ReactNode = null;

  if (style === "subtitle_bottom_center") {
    const cue = cues.find((c) => ms >= c.startMs && ms <= c.endMs);
    if (cue) body = <span>{cue.text}</span>;
  } else {
    const activeIdx = words.findIndex((w) => ms >= w.startMs && ms <= w.endMs);
    if (activeIdx >= 0) {
      const start = Math.max(0, activeIdx - Math.floor(maxWords / 2));
      const window = words.slice(start, start + maxWords);
      body = (
        <span>
          {window.map((w, i) => {
            const isActive = start + i === activeIdx;
            const color =
              style === "word_highlight_yellow"
                ? isActive
                  ? accent
                  : "#fff"
                : style === "karaoke_colored"
                  ? start + i <= activeIdx
                    ? accent
                    : "#fff"
                  : "#fff";
            return (
              <span key={start + i} style={{ color, marginRight: "0.35em" }}>
                {w.text}
              </span>
            );
          })}
        </span>
      );
    }
  }

  if (!body) return null;

  const fontSize = style === "big_bold_shorts" ? 120 : 72;
  const bottom = style === "big_bold_shorts" ? "50%" : 120;
  const transform = style === "big_bold_shorts" ? "translateY(50%)" : undefined;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom,
          transform,
          padding: "0 80px",
          ...BASE_TEXT,
          fontSize,
        }}
      >
        {body}
      </div>
    </AbsoluteFill>
  );
};
