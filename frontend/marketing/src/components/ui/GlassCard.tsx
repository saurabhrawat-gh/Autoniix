"use client";

import { cn } from "@/lib/utils";
import { useRef, useState } from "react";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  children: React.ReactNode;
}

export default function GlassCard({ hover = false, className, children, style, ...props }: GlassCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState("");
  const [glowPos, setGlowPos] = useState({ x: 50, y: 50 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!hover) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xPct = (e.clientX - rect.left) / rect.width;
    const yPct = (e.clientY - rect.top) / rect.height;
    const rotateX = (0.5 - yPct) * 10;
    const rotateY = (xPct - 0.5) * 10;
    setTilt(`perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(8px)`);
    setGlowPos({ x: xPct * 100, y: yPct * 100 });
  };

  const handleMouseLeave = () => {
    setTilt("perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0px)");
  };

  return (
    <div
      ref={ref}
      className={cn("glass-card rounded-2xl relative overflow-hidden", hover && "cursor-pointer", className)}
      style={{
        transform: hover ? tilt : undefined,
        transition: "transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease",
        ...style,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {/* Mouse-tracking inner glow */}
      {hover && (
        <div
          className="pointer-events-none absolute inset-0 opacity-0 hover:opacity-100 transition-opacity duration-300 rounded-2xl"
          style={{
            background: `radial-gradient(200px circle at ${glowPos.x}% ${glowPos.y}%, rgba(0,216,159,0.07), transparent 70%)`,
          }}
        />
      )}
      {children}
    </div>
  );
}
