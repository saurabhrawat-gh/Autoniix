/**
 * Diff render cache (P0.3).
 *
 * Keyed by `hash(sub-scene-graph) + tierVersion + codec + resolution + fps`.
 * Lookup before each shard dispatch; write on success.
 *
 * The cache is stored in the same S3/MinIO bucket as renders, under the
 * prefix `frames/`. Layout:
 *
 *   frames/<cacheKey>.mp4    ← rendered shard payload
 *   frames/<cacheKey>.meta   ← optional sidecar metadata (json)
 *
 * Activated by env.DIFF_CACHE_ENABLED. When disabled, every helper is a
 * no-op so callers can be wired unconditionally.
 *
 * NOTE: this module wraps the existing S3 client used by `uploadFile`. It
 * deliberately does not introduce a new client to keep configuration matrix
 * small.
 */

import {
  CopyObjectCommand,
  GetObjectCommand,
  HeadObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { createReadStream, createWriteStream, statSync } from "node:fs";
import { pipeline } from "node:stream/promises";
import type { Readable } from "node:stream";
import { env } from "./env";
import { logger } from "./logger";
import { sha256Hex } from "../scene-graph/hash";

/** Bumped any time the renderer output bytes can change for the same input
 *  (codec defaults, postRenderQc filter changes, ffmpeg upgrade). Adding to
 *  this string invalidates all cached frames atomically. */
export const TIER_VERSION = "t1@2026.05";

let client: S3Client | null = null;
function getClient(): S3Client {
  if (client) return client;
  client = new S3Client({
    region: env.S3_REGION,
    endpoint: env.S3_ENDPOINT || undefined,
    forcePathStyle: env.S3_FORCE_PATH_STYLE,
    credentials:
      env.S3_ACCESS_KEY_ID && env.S3_SECRET_ACCESS_KEY
        ? { accessKeyId: env.S3_ACCESS_KEY_ID, secretAccessKey: env.S3_SECRET_ACCESS_KEY }
        : undefined,
  });
  return client;
}

export interface DiffCacheKeyInput {
  shardHash: string;
  tier: "t0" | "t1" | "t2";
  codec: string;
  width: number;
  height: number;
  fps: number;
}

export function buildCacheKey(k: DiffCacheKeyInput): string {
  const composite = [k.shardHash, TIER_VERSION, k.tier, k.codec, k.width, k.height, k.fps].join("|");
  return sha256Hex(composite);
}

function s3Key(cacheKey: string): string {
  const prefix = env.S3_KEY_PREFIX.replace(/^\/+|\/+$/g, "");
  const base = `frames/${cacheKey}.mp4`;
  return prefix ? `${prefix}/${base}` : base;
}

export interface CacheLookupResult {
  hit: boolean;
  s3Key?: string;
  size?: number;
}

export async function lookupShard(input: DiffCacheKeyInput): Promise<CacheLookupResult> {
  if (!env.DIFF_CACHE_ENABLED) return { hit: false };
  const cacheKey = buildCacheKey(input);
  const Key = s3Key(cacheKey);
  try {
    const head = await getClient().send(new HeadObjectCommand({ Bucket: env.S3_BUCKET, Key }));
    return { hit: true, s3Key: Key, size: head.ContentLength };
  } catch (err: unknown) {
    if (isNotFound(err)) return { hit: false };
    logger.warn({ err, Key }, "diff-cache lookup failed (treating as miss)");
    return { hit: false };
  }
}

export async function downloadShard(s3KeyValue: string, destPath: string): Promise<number> {
  const out = await getClient().send(new GetObjectCommand({ Bucket: env.S3_BUCKET, Key: s3KeyValue }));
  const body = out.Body as Readable | undefined;
  if (!body) throw new Error("diff-cache: empty body on cached shard");
  await pipeline(body, createWriteStream(destPath));
  return statSync(destPath).size;
}

export async function storeShard(
  input: DiffCacheKeyInput,
  localPath: string,
  contentType = "video/mp4",
): Promise<{ s3Key: string; size: number } | undefined> {
  if (!env.DIFF_CACHE_ENABLED) return undefined;
  const cacheKey = buildCacheKey(input);
  const Key = s3Key(cacheKey);
  const size = statSync(localPath).size;
  await getClient().send(
    new PutObjectCommand({
      Bucket: env.S3_BUCKET,
      Key,
      Body: createReadStream(localPath),
      ContentType: contentType,
      Metadata: {
        "x-shard-hash": input.shardHash,
        "x-tier": input.tier,
        "x-codec": input.codec,
        "x-tier-version": TIER_VERSION,
      },
    }),
  );
  return { s3Key: Key, size };
}

/** Promote a cached shard into the final render's shard slot (cheap copy
 *  inside the bucket). Useful when the concat job needs all shards under a
 *  predictable prefix (`renders/<renderId>/shard-<i>.mp4`). */
export async function promoteToRender(s3Source: string, s3Dest: string): Promise<void> {
  await getClient().send(
    new CopyObjectCommand({
      Bucket: env.S3_BUCKET,
      CopySource: `${env.S3_BUCKET}/${encodeURIComponent(s3Source)}`,
      Key: s3Dest,
    }),
  );
}

function isNotFound(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { name?: string; $metadata?: { httpStatusCode?: number } };
  return e.name === "NotFound" || e.$metadata?.httpStatusCode === 404;
}
