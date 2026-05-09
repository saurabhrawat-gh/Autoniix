/**
 * Canonicalization + sha256 for SceneGraph nodes.
 *
 * Rules:
 *  - `undefined` fields are stripped (they are equivalent to absent).
 *  - Object keys are sorted lexicographically.
 *  - Arrays preserve order (order is semantically meaningful for tracks/clips).
 *  - Numbers are serialized as JSON (no rounding — caller must normalize first).
 *  - `hash` fields are EXCLUDED during hashing to avoid self-reference.
 *  - `meta.sourceDirection` is hashed as an opaque string prefix to keep the
 *    canonicalizer small; changing direction-v3 content of course changes the
 *    hash.
 */

import { createHash } from "node:crypto";

/** Stable stringify with sorted keys and `hash`-field exclusion. */
export function canonicalize(value: unknown): string {
  return _stringify(value);
}

function _stringify(v: unknown): string {
  if (v === null) return "null";
  if (v === undefined) return "null"; // we strip undefined at object level; this path only for root
  const t = typeof v;
  if (t === "number") {
    if (!Number.isFinite(v as number)) throw new Error("non-finite number in canonicalize");
    return JSON.stringify(v);
  }
  if (t === "string" || t === "boolean") return JSON.stringify(v);
  if (t === "bigint") return JSON.stringify((v as bigint).toString());
  if (Array.isArray(v)) {
    return "[" + v.map((x) => _stringify(x)).join(",") + "]";
  }
  if (t === "object") {
    const obj = v as Record<string, unknown>;
    const keys = Object.keys(obj)
      .filter((k) => obj[k] !== undefined && k !== "hash")
      .sort();
    const body = keys
      .map((k) => JSON.stringify(k) + ":" + _stringify(obj[k]))
      .join(",");
    return "{" + body + "}";
  }
  throw new Error(`unserializable value in canonicalize: ${t}`);
}

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

/** Hash any serializable value by canonicalizing and hashing. */
export function hashNode(node: unknown): string {
  return sha256Hex(canonicalize(node));
}
