/**
 * Hardware encoder routing (P0.4).
 *
 * Detects which ffmpeg encoders are available on the host and picks the best
 * one for the requested codec, honouring `env.ENCODER_HINT`.
 *
 * Remotion's `renderMedia({ codec })` supports the codec FAMILY (h264, h265,
 * vp8, vp9). Hardware acceleration is selected via `hardwareAcceleration` in
 * Remotion 4.x. If a host has no hardware path, we fall back transparently
 * to the software default (libx264 / libx265 / libvpx*).
 */

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { logger } from "./logger";
import { env } from "./env";

const execFileAsync = promisify(execFile);

export type CodecFamily = "h264" | "h265" | "vp8" | "vp9";
export type EncoderName =
  | "libx264"
  | "h264_nvenc"
  | "h264_qsv"
  | "h264_vaapi"
  | "libx265"
  | "hevc_nvenc"
  | "hevc_qsv"
  | "hevc_vaapi"
  | "libvpx"
  | "libvpx-vp9";

/** Remotion 4.x hardwareAcceleration options. */
export type RemotionHwAccel = "if-possible" | "required" | "disable";

export interface EncoderSelection {
  codec: CodecFamily;
  encoder: EncoderName;
  hardwareAcceleration: RemotionHwAccel;
  /** Adjusted CRF (NVENC tends to need ~+2 over libx264 at equal perceptual quality). */
  crfOffset: number;
  /** True if the picked encoder is hardware-accelerated. */
  isHardware: boolean;
}

let cachedAvailable: Set<EncoderName> | null = null;

export async function detectEncoders(): Promise<Set<EncoderName>> {
  if (cachedAvailable) return cachedAvailable;
  const set = new Set<EncoderName>();
  try {
    const { stdout } = await execFileAsync("ffmpeg", ["-hide_banner", "-encoders"], { maxBuffer: 4 * 1024 * 1024 });
    const candidates: EncoderName[] = [
      "libx264",
      "h264_nvenc",
      "h264_qsv",
      "h264_vaapi",
      "libx265",
      "hevc_nvenc",
      "hevc_qsv",
      "hevc_vaapi",
      "libvpx",
      "libvpx-vp9",
    ];
    for (const name of candidates) {
      const re = new RegExp(`\\b${escapeRegex(name)}\\b`);
      if (re.test(stdout)) set.add(name);
    }
  } catch (err) {
    logger.warn({ err }, "encoder detection failed; assuming libx264 only");
    set.add("libx264");
  }
  cachedAvailable = set;
  return set;
}

export async function selectEncoder(codec: CodecFamily): Promise<EncoderSelection> {
  const available = await detectEncoders();
  const hint = env.ENCODER_HINT.toLowerCase();

  if (hint !== "auto") {
    const forced = forcedFromHint(hint, codec, available);
    if (forced) return forced;
    logger.warn({ hint, codec }, "ENCODER_HINT not available for codec; falling back to auto");
  }

  for (const enc of preferenceOrder(codec)) {
    if (available.has(enc)) {
      return wrap(codec, enc);
    }
  }
  return wrap(codec, fallback(codec));
}

function preferenceOrder(codec: CodecFamily): EncoderName[] {
  switch (codec) {
    case "h264":
      return ["h264_nvenc", "h264_qsv", "h264_vaapi", "libx264"];
    case "h265":
      return ["hevc_nvenc", "hevc_qsv", "hevc_vaapi", "libx265"];
    case "vp9":
      return ["libvpx-vp9"];
    case "vp8":
      return ["libvpx"];
  }
}

function fallback(codec: CodecFamily): EncoderName {
  switch (codec) {
    case "h264":
      return "libx264";
    case "h265":
      return "libx265";
    case "vp9":
      return "libvpx-vp9";
    case "vp8":
      return "libvpx";
  }
}

function forcedFromHint(
  hint: string,
  codec: CodecFamily,
  available: Set<EncoderName>,
): EncoderSelection | null {
  const map: Record<string, Partial<Record<CodecFamily, EncoderName>>> = {
    nvenc: { h264: "h264_nvenc", h265: "hevc_nvenc" },
    qsv: { h264: "h264_qsv", h265: "hevc_qsv" },
    vaapi: { h264: "h264_vaapi", h265: "hevc_vaapi" },
    x264: { h264: "libx264" },
    x265: { h265: "libx265" },
  };
  const enc = map[hint]?.[codec];
  if (enc && available.has(enc)) return wrap(codec, enc);
  return null;
}

function wrap(codec: CodecFamily, encoder: EncoderName): EncoderSelection {
  const isHardware = encoder !== "libx264" && encoder !== "libx265" && encoder !== "libvpx" && encoder !== "libvpx-vp9";
  return {
    codec,
    encoder,
    hardwareAcceleration: isHardware ? "if-possible" : "disable",
    crfOffset: encoder === "h264_nvenc" || encoder === "hevc_nvenc" ? 2 : 0,
    isHardware,
  };
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
