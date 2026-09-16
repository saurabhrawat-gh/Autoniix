"use client";

import { useEffect, useRef } from "react";

export default function CursorSpotlight() {
  const largeRef = useRef<HTMLDivElement>(null);
  const smallRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let rafId: number;
    let mouseX = -1000;
    let mouseY = -1000;
    let largeX = -1000;
    let largeY = -1000;

    const onMove = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (smallRef.current) {
        smallRef.current.style.transform = `translate(${mouseX - 50}px, ${mouseY - 50}px)`;
        smallRef.current.style.opacity = "1";
      }
    };

    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

    const tick = () => {
      largeX = lerp(largeX, mouseX, 0.05);
      largeY = lerp(largeY, mouseY, 0.05);
      if (largeRef.current) {
        largeRef.current.style.transform = `translate(${largeX - 400}px, ${largeY - 400}px)`;
      }
      rafId = requestAnimationFrame(tick);
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    rafId = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <>
      {/* Large soft ambient glow — follows with lag */}
      <div
        ref={largeRef}
        className="fixed top-0 left-0 pointer-events-none z-[1] w-[800px] h-[800px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(0,216,159,0.035) 0%, transparent 65%)",
          willChange: "transform",
        }}
      />
      {/* Small sharp spotlight — follows cursor directly */}
      <div
        ref={smallRef}
        className="fixed top-0 left-0 pointer-events-none z-[1] w-[100px] h-[100px] rounded-full opacity-0 transition-opacity duration-300"
        style={{
          background: "radial-gradient(circle, rgba(0,216,159,0.08) 0%, transparent 75%)",
          willChange: "transform",
        }}
      />
    </>
  );
}
