export interface SrtCue {
  index: number;
  startMs: number;
  endMs: number;
  text: string;
}

export interface SrtWord {
  startMs: number;
  endMs: number;
  text: string;
}

const timecodeToMs = (tc: string): number => {
  const m = tc.match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
  if (!m) return 0;
  return (
    Number(m[1]) * 3_600_000 + Number(m[2]) * 60_000 + Number(m[3]) * 1000 + Number(m[4])
  );
};

/**
 * Parses SRT / WebVTT-ish content. Supports both `,` and `.` millisecond
 * separators and ignores leading WEBVTT header lines.
 */
export function parseSrt(content: string): SrtCue[] {
  const blocks = content
    .replace(/\r\n/g, "\n")
    .replace(/^WEBVTT.*?\n/s, "")
    .split(/\n\n+/)
    .map((b) => b.trim())
    .filter(Boolean);

  const cues: SrtCue[] = [];
  for (const block of blocks) {
    const lines = block.split("\n");
    let index = 0;
    let timeLine = "";
    let textLines: string[] = [];

    if (/^\d+$/.test(lines[0] ?? "")) {
      index = Number(lines[0]);
      timeLine = lines[1] ?? "";
      textLines = lines.slice(2);
    } else {
      timeLine = lines[0] ?? "";
      textLines = lines.slice(1);
    }

    const [start, end] = timeLine.split(/\s*-->\s*/);
    if (!start || !end) continue;

    cues.push({
      index,
      startMs: timecodeToMs(start),
      endMs: timecodeToMs(end),
      text: textLines.join(" ").replace(/<[^>]+>/g, "").trim(),
    });
  }
  return cues;
}

/**
 * Approximates per-word timing by splitting each cue's duration evenly across
 * its words. Good enough until real forced-alignment is wired (Phase 3).
 */
export function wordsFromCues(cues: SrtCue[]): SrtWord[] {
  const out: SrtWord[] = [];
  for (const cue of cues) {
    const words = cue.text.split(/\s+/).filter(Boolean);
    if (words.length === 0) continue;
    const per = (cue.endMs - cue.startMs) / words.length;
    words.forEach((w, i) => {
      out.push({
        startMs: Math.round(cue.startMs + i * per),
        endMs: Math.round(cue.startMs + (i + 1) * per),
        text: w,
      });
    });
  }
  return out;
}
