# Remotion Renderer — Design Docs

Planning artifacts for the YT-automation Remotion renderer. Read in order:

1. **[A. Component & Preset Registry](./A-component-preset-registry.md)** — full list: 121 components, 400+ presets across scenes, transitions, animations, effects, overlays, branding, audio, templates.
2. **[B. Build Plan](./B-build-plan.md)** — Phases 0–5, week-by-week scope, effort estimate, risks.
3. **[C. Preset Registry Pattern](./C-preset-registry-pattern.md)** — code pattern showing how 1 component file → 20+ named presets. Resolver, variant generator, usage examples.
4. **[D. Direction Format v3 JSON Schema](./D-direction-format-v3-schema.md)** — contract between AI director and renderer. Zod validator, template-aware rules.

## Key decision

**Preset-first architecture.** Every scene/transition/animation/effect the AI director picks is a string ID like `trans.slide.left.fast` or `scene.kinetic.scale_punch`. Adding a new variant = 4 lines in a registry file, not a new component. This is how we scale from MVP (~55 presets) to CapCut-class (1000+) without exploding the codebase.

## Next steps (when you're ready)

- Scaffold Phase 0 (repo + `registry/` + API skeleton + Docker)
- Build Phase 1 MVP (~2 weeks): 6 scenes, 5 transitions, 6 animations, captions, audio mixer → first production renders
