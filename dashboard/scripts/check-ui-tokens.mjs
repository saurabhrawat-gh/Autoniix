#!/usr/bin/env node
/**
 * Token lint
 *
 * Pass 1 (HARD — exits non-zero):
 *   Any file under dashboard/src/lib/ui/ must not use raw color literals
 *   (#hex, rgb()/rgba()/hsl()/hsla() except `var(--...)`-backed).
 *
 * Pass 2 (SOFT — warning, exits 0):
 *   Any file under dashboard/src/app/dashboard/ should not use raw Tailwind
 *   status-semantic palette classes (text-emerald-500, bg-red-500/10, etc.).
 *   Use the status tokens (text-status-success / bg-status-error / etc.) or
 *   accent tokens instead.
 *
 *   Files in PASS2_ALLOWLIST are exempt — they use Tailwind palette colors
 *   for decorative classification (file-type icons, scope chips, template
 *   accents) where the color encodes information independent of status.
 *
 * Pass the `--strict` flag to make Pass 2 hard-fail too.
 *
 * Allowed: `bg-surface-0`, `text-content-primary`, `border-border`,
 *          `bg-accent/10`, `shadow-elevated`, `rgb(var(--accent) / 0.5)`.
 * Disallowed in Pass 1: `#fff`, `#1e2026`, `rgb(0, 151, 111)`, `hsl(...)`.
 *
 * Run: `node scripts/check-ui-tokens.mjs` from dashboard/.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const STRICT = process.argv.includes('--strict');
const UI_ROOT = new URL('../src/lib/ui/', import.meta.url).pathname;
const PAGES_ROOT = new URL('../src/app/dashboard/', import.meta.url).pathname;

const HEX = /#[0-9a-fA-F]{3,8}\b/g;
// rgb(...) / rgba(...) / hsl(...) / hsla(...) that does NOT contain `var(--`
const RAW_COLOR_FN = /\b(?:rgba?|hsla?)\s*\(\s*(?!var\(--)[^)]*\)/g;

// Tailwind status-semantic palette colors that should be replaced by tokens.
// We deliberately do not flag every palette — only the ones with status
// semantics (emerald/red/amber/orange) or that are commonly misused for
// status (blue/violet). Slate / gray / zinc shades are allowed as content
// neutrals when needed (typography only).
const RAW_PALETTE = /\b(?:text|bg|border|ring|fill|stroke|from|to|via)-(?:emerald|red|amber|orange|rose|green|lime)-(?:50|100|200|300|400|500|600|700|800|900|950)(?:\/\d{1,3})?\b/g;

// Files where decorative colors are intentional (informational, not status).
// In each case the palette color encodes per-item identity (avatar hash,
// section nav, file-type) rather than success/warning/error semantics.
const PASS2_ALLOWLIST = new Set([
  'src/app/dashboard/library/page.tsx',          // file-type kind-icon colors
  'src/app/dashboard/experiments/page.tsx',      // template accent identity per card
  'src/app/dashboard/channels/page.tsx',         // AVATAR_COLORS hash palette
  'src/app/dashboard/page.tsx',                  // quick-nav per-section identity colors
]);

const hardViolations = [];
const softViolations = [];

function walk(dir, cb) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) walk(p, cb);
    else if (/\.(tsx?|jsx?|css)$/.test(entry)) cb(p);
  }
}

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

function checkUi(file) {
  const stripped = stripComments(readFileSync(file, 'utf8'));
  for (const re of [HEX, RAW_COLOR_FN]) {
    let m;
    re.lastIndex = 0;
    while ((m = re.exec(stripped))) {
      const idx = m.index;
      const ctx = stripped.slice(Math.max(0, idx - 20), idx + 40);
      if (ctx.includes('data:image/svg')) continue;
      hardViolations.push({ file: relative(process.cwd(), file), match: m[0], ctx: ctx.replace(/\s+/g, ' ').trim() });
    }
  }
}

function checkPages(file) {
  const rel = relative(process.cwd(), file).replace(/\\/g, '/');
  if (PASS2_ALLOWLIST.has(rel)) return;
  const stripped = stripComments(readFileSync(file, 'utf8'));
  let m;
  RAW_PALETTE.lastIndex = 0;
  while ((m = RAW_PALETTE.exec(stripped))) {
    const idx = m.index;
    const ctx = stripped.slice(Math.max(0, idx - 30), idx + 50);
    softViolations.push({ file: rel, match: m[0], ctx: ctx.replace(/\s+/g, ' ').trim() });
  }
}

walk(UI_ROOT, checkUi);
walk(PAGES_ROOT, checkPages);

let hardFail = false;

if (hardViolations.length) {
  hardFail = true;
  console.error(`\n❌ UI token lint (Pass 1) — ${hardViolations.length} raw color literal(s) in lib/ui/:\n`);
  for (const v of hardViolations) {
    console.error(`  ${v.file}: ${v.match}`);
    console.error(`    … ${v.ctx} …`);
  }
  console.error('\nUse token classes (bg-surface-*, text-content-*, etc.) instead.');
} else {
  console.log('✓ Pass 1 — lib/ui/ uses only token classes.');
}

if (softViolations.length) {
  const label = STRICT ? '❌' : '⚠ ';
  console.error(`\n${label} UI token lint (Pass 2) — ${softViolations.length} raw status palette class(es) in dashboard/:\n`);
  // Group by file for readability
  const byFile = new Map();
  for (const v of softViolations) {
    if (!byFile.has(v.file)) byFile.set(v.file, []);
    byFile.get(v.file).push(v);
  }
  for (const [f, list] of byFile) {
    console.error(`  ${f} (${list.length}):`);
    for (const v of list.slice(0, 6)) console.error(`    ${v.match}`);
    if (list.length > 6) console.error(`    … +${list.length - 6} more`);
  }
  console.error('\nUse status tokens: text-status-{success|error|warning|info}, bg-status-*, border-status-*.');
  console.error('Whitelist intentional decorative usage in PASS2_ALLOWLIST in scripts/check-ui-tokens.mjs.\n');
  if (STRICT) hardFail = true;
} else {
  console.log('✓ Pass 2 — dashboard pages use status tokens only.');
}

process.exit(hardFail ? 1 : 0);
