# scene-graph — SceneGraph IR

Internal module (P0.1 of the remotion-vision plan). Lowers `DirectionV3` into a
typed, hashable, agent-mutable intermediate representation that all future
renderer tiers (T0 WebGPU / T1 Chromium / T2 ffmpeg-direct) consume.

See `docs/future/remotion-vision/02-FUTURE-ENGINE-ARCHITECTURE.md` sections 2.3–2.4.

## Surface

```ts
import { lower, hashGraph, normalizeGraph, SceneGraph } from "./scene-graph";

const graph = lower(directionV3);   // pure function, deterministic
const h = hashGraph(graph);         // sha256 over canonicalized form
```

## Guarantees

1. **Determinism**: `lower(d) === lower(d)` byte-for-byte.
2. **Canonical hashing**: `hashGraph(g) === hashGraph(g')` iff `g` and `g'` are
   semantically equivalent (same ordered clips, same props, same audio graph).
3. **Backwards-compatible dispatch**: a `SceneGraph` always carries the
   original `directionV3` payload under `graph.meta.sourceDirection` so the
   legacy Tier-1 render path continues to work unchanged during rollout.

## Files

- `types.ts`    — IR node types
- `hash.ts`     — canonicalizer + sha256
- `lower.ts`    — `directionV3 → SceneGraph`
- `capability.ts` — per-clip capability flags for the tier router (P0.9)
- `index.ts`    — public surface

## Tests

Co-located as `*.test.ts` (P0.1 exit criteria: property tests + 100-fixture
bit-identity gate; fixture harness scaffolded in `scripts/scene-graph-golden.ts`).
