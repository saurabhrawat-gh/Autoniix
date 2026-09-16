import { TEMPLATES } from "../templates";
import type { DirectionV3Input } from "../schemas/directionV3";

export interface ValidationReport {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Enforces template rules (forbidden transitions, scene-category ratio budgets).
 * Pure function — intended to run on the worker before render.
 */
export function validateAgainstTemplate(d: DirectionV3Input): ValidationReport {
  const errors: string[] = [];
  const warnings: string[] = [];

  const tpl = TEMPLATES[d.template];
  if (!tpl) {
    warnings.push(`Unknown template "${d.template}" — skipping template validation.`);
    return { valid: true, errors, warnings };
  }

  for (const seg of d.segments) {
    const tId = seg.transition_out?.preset;
    if (!tId) continue;

    if (tpl.forbidden_transition_prefixes?.some((p) => tId.startsWith(p))) {
      errors.push(`Segment ${seg.id}: transition "${tId}" is forbidden by template "${tpl.id}".`);
    }
    if (
      tpl.allowed_transition_prefixes &&
      !tpl.allowed_transition_prefixes.some((p) => tId.startsWith(p))
    ) {
      warnings.push(
        `Segment ${seg.id}: transition "${tId}" is not in the allowed list for template "${tpl.id}".`,
      );
    }
  }

  if (tpl.ratio_budgets) {
    const totalMs = d.segments.reduce((a, s) => a + s.duration_ms, 0);
    const byCat: Record<string, number> = {};
    for (const s of d.segments) {
      const parts = s.scene_preset.split(".");
      const cat = parts[1] ?? "unknown";
      byCat[cat] = (byCat[cat] ?? 0) + s.duration_ms;
    }
    for (const [cat, [min, max]] of Object.entries(tpl.ratio_budgets)) {
      const ratio = (byCat[cat] ?? 0) / Math.max(1, totalMs);
      if (ratio < min) {
        warnings.push(
          `Template "${tpl.id}": category "${cat}" ratio ${ratio.toFixed(2)} below target ${min}.`,
        );
      }
      if (ratio > max) {
        warnings.push(
          `Template "${tpl.id}": category "${cat}" ratio ${ratio.toFixed(2)} above target ${max}.`,
        );
      }
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}
