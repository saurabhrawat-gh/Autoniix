"use client";

import { motion, type HTMLMotionProps } from "framer-motion";

const EASE = [0.16, 1, 0.3, 1] as const;

/** Scroll-triggered fade/rise. Wrap any block; children render once in view. */
export default function Reveal({
  delay = 0,
  y = 24,
  children,
  ...rest
}: HTMLMotionProps<"div"> & { delay?: number; y?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, delay, ease: EASE }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
