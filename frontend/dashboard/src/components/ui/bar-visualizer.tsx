"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface BarVisualizerProps {
  barCount?: number;
  barHeights?: number[];
  color?: string;
  className?: string;
}

export function BarVisualizer({
  barCount = 5,
  barHeights = [],
  color = "rgb(var(--accent))",
  className,
}: BarVisualizerProps) {
  const reduce = useReducedMotion();

  return (
    <div className={cn("flex items-end gap-0.5", className)}>
      {Array.from({ length: barCount }, (_, i) => {
        const hPct = Math.max(10, (barHeights[i] ?? 0) * 100);
        return (
          <motion.div
            key={i}
            className="flex-1 rounded-full"
            style={{ background: color, minHeight: 3 }}
            animate={{ height: reduce ? "10%" : `${hPct}%` }}
            transition={{ duration: 0.35, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
          />
        );
      })}
    </div>
  );
}
