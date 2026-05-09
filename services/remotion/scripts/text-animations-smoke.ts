/**
 * Phase 1B — Pure-compute smoke test for the 6 advanced text animations.
 *
 * Usage:
 *   cd services/remotion && npx tsx scripts/text-animations-smoke.ts
 *
 * Asserts (per animation):
 *   • Boundary correctness  (output at t=0 vs t=duration matches expectation)
 *   • Determinism           (two runs with the same params yield identical output)
 *   • Monotonic progress    (where applicable)
 *
 * Exits non-zero on any failure.
 */

import {
  ADVANCED_TEXT_ANIM_KINDS,
  computeCountUp,
  computePathFollow,
  computeScrambleDecode,
  computeStaggerWords,
  computeTypewriter,
  computeWave,
} from "../src/registry/textAnimations";

let failures = 0;
function check(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failures += 1;
  }
}

/* ---- 1. count_up ------------------------------------------------------ */
{
  const params = {
    fromValue: 3,
    toValue: 12,
    durationMs: 1000,
    decimals: 2,
    format: "$${value}",
    easing: "ease_out_cubic" as const,
  };
  const a = computeCountUp(params, 0);
  const b = computeCountUp(params, 500);
  const c = computeCountUp(params, 1000);
  const d = computeCountUp(params, 2000);
  check(a.value === 3 && a.text === "$3.00", `count_up start: ${JSON.stringify(a)}`);
  check(c.value === 12 && c.text === "$12.00", `count_up end: ${JSON.stringify(c)}`);
  check(d.value === 12, `count_up clamps after duration: ${JSON.stringify(d)}`);
  check(b.value > a.value && b.value < c.value, `count_up midpoint monotonic`);
  // Determinism
  const a2 = computeCountUp(params, 0);
  const b2 = computeCountUp(params, 500);
  check(a.text === a2.text && b.text === b2.text, `count_up determinism`);
}

/* ---- 2. typewriter ---------------------------------------------------- */
{
  const params = { text: "Hello, world!", cps: 13, cursorChar: "▎" };
  const a = computeTypewriter(params, 0);
  const mid = computeTypewriter(params, 500); // 6.5 chars -> floor 6
  const end = computeTypewriter(params, 1100);
  check(a.visible === "" && a.progress === 0, `typewriter at t=0`);
  check(mid.visible === "Hello," || mid.visible === "Hello,", `typewriter midpoint: ${mid.visible}`);
  check(end.visible === "Hello, world!" && end.progress === 1, `typewriter end`);
  // Cursor blink
  const cur1 = computeTypewriter(params, 200);
  const cur2 = computeTypewriter(params, 700);
  check(cur1.showCursor !== cur2.showCursor, `typewriter cursor blinks`);
}

/* ---- 3. scramble_decode ----------------------------------------------- */
{
  const text = "DECODE";
  const params = {
    text,
    durationMs: 600,
    revealMode: "left_to_right" as const,
    seed: "smoke-1",
    scrambleFps: 20,
  };
  const a = computeScrambleDecode(params, 0);
  const mid = computeScrambleDecode(params, 300);
  const end = computeScrambleDecode(params, 600);
  const after = computeScrambleDecode(params, 1200);
  check(a.visible.length === text.length, `scramble length stable @t=0`);
  check(end.visible === text, `scramble settles to ${text} at duration`);
  check(after.visible === text, `scramble stays at ${text} past duration`);
  // Left-to-right means at midpoint the FIRST half should be settled,
  // the SECOND half still scrambled (or just-settled).
  const settledPrefix = mid.visible.slice(0, 3);
  check(settledPrefix === text.slice(0, 3), `LTR midpoint: prefix settled (${mid.visible})`);
  // Determinism
  const a2 = computeScrambleDecode(params, 100);
  const a3 = computeScrambleDecode(params, 100);
  check(a2.visible === a3.visible, `scramble determinism @ t=100`);
  // Random mode determinism with seed
  const r1 = computeScrambleDecode(
    { ...params, revealMode: "random", seed: "fixed" },
    150,
  );
  const r2 = computeScrambleDecode(
    { ...params, revealMode: "random", seed: "fixed" },
    150,
  );
  check(r1.visible === r2.visible, `scramble random-mode determinism`);
}

/* ---- 4. path_follow --------------------------------------------------- */
{
  const path = {
    start: [0, 100] as [number, number],
    segments: [
      { c1: [50, 0] as [number, number], c2: [150, 0] as [number, number], end: [200, 100] as [number, number] },
    ],
  };
  const params = { text: "ARC", path, spread: 1, alignToPath: true };
  const glyphs = computePathFollow(params, 0);
  check(glyphs.length === 3, `path_follow glyph count`);
  check(glyphs[0]!.x === 0 && glyphs[0]!.y === 100, `first glyph at start: ${JSON.stringify(glyphs[0])}`);
  check(
    Math.abs(glyphs[2]!.x - 200) < 0.001 && Math.abs(glyphs[2]!.y - 100) < 0.001,
    `last glyph at end: ${JSON.stringify(glyphs[2])}`,
  );
  check(glyphs[1]!.y < 100, `middle glyph elevated by curve (y=${glyphs[1]!.y})`);
  // Determinism
  const g2 = computePathFollow(params, 0);
  check(JSON.stringify(g2) === JSON.stringify(glyphs), `path_follow determinism`);
  // Spread = 0 should collapse all glyphs to the start.
  const collapsed = computePathFollow({ ...params, spread: 0 }, 0);
  check(
    collapsed.every((g) => g.x === path.start[0] && g.y === path.start[1]),
    `spread=0 collapses to start`,
  );
}

/* ---- 5. stagger_words ------------------------------------------------- */
{
  const params = {
    words: ["Three", "hidden", "lessons"],
    delayPerWordMs: 200,
    wordDurationMs: 300,
  };
  const a = computeStaggerWords(params, 0);
  check(
    a.perWord[0]!.progress === 0 &&
      !a.perWord[1]!.started &&
      !a.perWord[2]!.started,
    `stagger @t=0: only first word at start`,
  );
  const b = computeStaggerWords(params, 250);
  check(
    b.perWord[0]!.progress > 0 && b.perWord[0]!.progress < 1,
    `stagger @t=250: word 0 mid-progress`,
  );
  check(b.perWord[1]!.started, `stagger @t=250: word 1 started`);
  check(!b.perWord[2]!.started, `stagger @t=250: word 2 not yet started`);
  const c = computeStaggerWords(params, 1000);
  check(c.perWord.every((w) => w.finished), `stagger @t=1000: all finished`);
}

/* ---- 6. wave ---------------------------------------------------------- */
{
  const params = {
    text: "WAVES",
    amplitudePx: 10,
    frequencyHz: 1,
    wavelengthChars: 4,
  };
  const a = computeWave(params, 0);
  const b = computeWave(params, 250); // quarter cycle
  const c = computeWave(params, 1000); // full cycle
  check(a.length === 5, `wave glyph count`);
  // Each glyph should be in [-amp, +amp].
  check(
    a.every((g) => Math.abs(g.yOffsetPx) <= 10.0001),
    `wave amplitude bound`,
  );
  // Full cycle returns to ~same y as t=0.
  for (let i = 0; i < a.length; i++) {
    check(
      Math.abs(a[i]!.yOffsetPx - c[i]!.yOffsetPx) < 0.001,
      `wave full-cycle return: char ${i}`,
    );
  }
  // Determinism
  const b2 = computeWave(params, 250);
  check(
    b.every((g, i) => Math.abs(g.yOffsetPx - b2[i]!.yOffsetPx) < 1e-9),
    `wave determinism`,
  );
}

/* ---- Sanity: every advertised kind has a working compute -------------- */
const expectedKinds = new Set<string>([
  "count_up",
  "typewriter",
  "scramble_decode",
  "path_follow",
  "stagger_words",
  "wave",
]);
for (const kind of ADVANCED_TEXT_ANIM_KINDS) {
  check(expectedKinds.has(kind), `unexpected animation kind exposed: ${kind}`);
}
check(
  ADVANCED_TEXT_ANIM_KINDS.length === expectedKinds.size,
  `kind count: ${ADVANCED_TEXT_ANIM_KINDS.length} vs ${expectedKinds.size}`,
);

if (failures === 0) {
  console.log("OK text-animations smoke");
  console.log(
    `   animations:  ${ADVANCED_TEXT_ANIM_KINDS.length}  (count_up · typewriter · scramble · path · stagger · wave)`,
  );
} else {
  console.error(`\n${failures} text-animations check(s) failed.`);
  process.exit(1);
}
