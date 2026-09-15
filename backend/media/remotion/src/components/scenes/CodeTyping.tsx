import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export interface CodeTypingProps {
  code: string;
  language?: string;
  /** Characters per second. */
  cps?: number;
  theme?: "dark" | "light";
  fontSize?: number;
  title?: string;
  showLineNumbers?: boolean;
}

/**
 * Lightweight syntax-highlighting code typewriter. Uses a tiny tokenizer that
 * handles comments, strings, numbers, keywords, and identifiers — good enough
 * for JS/TS/Python/Go. For production-grade highlighting, swap in Shiki.
 */

const KEYWORDS = new Set([
  "const",
  "let",
  "var",
  "function",
  "return",
  "if",
  "else",
  "for",
  "while",
  "class",
  "interface",
  "type",
  "import",
  "export",
  "from",
  "as",
  "new",
  "await",
  "async",
  "try",
  "catch",
  "finally",
  "throw",
  "switch",
  "case",
  "break",
  "continue",
  "def",
  "lambda",
  "pass",
  "self",
  "null",
  "undefined",
  "true",
  "false",
  "nil",
  "None",
  "True",
  "False",
  "package",
  "func",
  "struct",
]);

type Tok = { text: string; kind: "kw" | "str" | "num" | "com" | "id" | "sym" };

function tokenize(src: string): Tok[] {
  const out: Tok[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i]!;

    if ((c === "/" && src[i + 1] === "/") || c === "#") {
      const j = src.indexOf("\n", i);
      const end = j === -1 ? src.length : j;
      out.push({ text: src.slice(i, end), kind: "com" });
      i = end;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      const j = src.indexOf("*/", i + 2);
      const end = j === -1 ? src.length : j + 2;
      out.push({ text: src.slice(i, end), kind: "com" });
      i = end;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < src.length && src[j] !== c) {
        if (src[j] === "\\") j++;
        j++;
      }
      out.push({ text: src.slice(i, Math.min(j + 1, src.length)), kind: "str" });
      i = j + 1;
      continue;
    }
    if (/\d/.test(c)) {
      let j = i;
      while (j < src.length && /[\d._a-fA-FxX]/.test(src[j]!)) j++;
      out.push({ text: src.slice(i, j), kind: "num" });
      i = j;
      continue;
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i;
      while (j < src.length && /[A-Za-z0-9_$]/.test(src[j]!)) j++;
      const word = src.slice(i, j);
      out.push({ text: word, kind: KEYWORDS.has(word) ? "kw" : "id" });
      i = j;
      continue;
    }
    out.push({ text: c, kind: "sym" });
    i++;
  }
  return out;
}

const THEMES = {
  dark: {
    bg: "#0d1117",
    fg: "#c9d1d9",
    kw: "#ff7b72",
    str: "#a5d6ff",
    num: "#79c0ff",
    com: "#8b949e",
    sym: "#c9d1d9",
    id: "#c9d1d9",
    gutter: "#484f58",
    chromeBg: "#161b22",
  },
  light: {
    bg: "#ffffff",
    fg: "#24292f",
    kw: "#cf222e",
    str: "#0a3069",
    num: "#0550ae",
    com: "#6e7781",
    sym: "#24292f",
    id: "#24292f",
    gutter: "#8c959f",
    chromeBg: "#f6f8fa",
  },
} as const;

export const CodeTyping: React.FC<CodeTypingProps> = ({
  code,
  language = "ts",
  cps = 30,
  theme = "dark",
  fontSize = 28,
  title,
  showLineNumbers = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const charsVisible = Math.min(code.length, Math.floor(t * cps));

  const typed = code.slice(0, charsVisible);
  const tokens = tokenize(typed);
  const pal = THEMES[theme];

  const lines = typed.split("\n");
  const showCursor = Math.floor(t * 2) % 2 === 0 && charsVisible < code.length;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: pal.bg,
        padding: 80,
        fontFamily: '"JetBrains Mono", "Fira Code", Menlo, monospace',
      }}
    >
      {/* IDE chrome */}
      <div
        style={{
          background: pal.chromeBg,
          padding: "14px 18px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderRadius: "12px 12px 0 0",
          borderBottom: `1px solid ${pal.gutter}30`,
        }}
      >
        <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#FF5F57" }} />
        <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#FEBC2E" }} />
        <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#28C840" }} />
        <div
          style={{
            marginLeft: 20,
            color: pal.fg,
            fontSize: 18,
            fontFamily: '"JetBrains Mono", monospace',
            opacity: 0.7,
          }}
        >
          {title ?? `main.${language}`}
        </div>
      </div>

      {/* Code block */}
      <div
        style={{
          background: pal.bg,
          padding: "32px 40px",
          borderRadius: "0 0 12px 12px",
          flex: 1,
          display: "flex",
          overflow: "hidden",
        }}
      >
        {showLineNumbers && (
          <div
            style={{
              color: pal.gutter,
              paddingRight: 24,
              borderRight: `1px solid ${pal.gutter}30`,
              marginRight: 24,
              fontSize,
              lineHeight: 1.55,
              textAlign: "right",
              minWidth: 48,
            }}
          >
            {lines.map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
        )}

        <div
          style={{
            flex: 1,
            fontSize,
            lineHeight: 1.55,
            color: pal.fg,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {tokens.map((tok, i) => (
            <span key={i} style={{ color: pal[tok.kind] }}>
              {tok.text}
            </span>
          ))}
          {showCursor && (
            <span
              style={{
                display: "inline-block",
                width: Math.max(2, fontSize * 0.08),
                height: fontSize,
                background: pal.fg,
                verticalAlign: "text-bottom",
                marginLeft: 2,
              }}
            />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
