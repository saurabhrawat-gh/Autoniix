import React from "react";
import { AbsoluteFill } from "remotion";
import { FadeIn } from "../animations/FadeIn";
import { ScaleIn } from "../animations/ScaleIn";
import { SlideIn } from "../animations/SlideIn";
import { Typewriter } from "../animations/Typewriter";

export type KineticAnim = "scale_punch" | "word_cascade" | "typewriter" | "fade_up";

export interface KineticTypographyProps {
  text: string;
  animation?: KineticAnim;
  /** CSS styling for the main text element. */
  style?: React.CSSProperties;
  bg?: string;
  color?: string;
  font?: string;
  weight?: number;
  size?: number;
  align?: "left" | "center" | "right";
}

export const KineticTypography: React.FC<KineticTypographyProps> = ({
  text,
  animation = "scale_punch",
  style,
  bg = "#0A0A0A",
  color = "#FFFFFF",
  font = "Inter, system-ui, sans-serif",
  weight = 900,
  size = 140,
  align = "center",
}) => {
  const textStyle: React.CSSProperties = {
    color,
    fontFamily: font,
    fontWeight: weight,
    fontSize: size,
    lineHeight: 1.05,
    letterSpacing: -2,
    textAlign: align,
    maxWidth: "85%",
    ...style,
  };

  let inner: React.ReactNode;

  if (animation === "scale_punch") {
    inner = (
      <ScaleIn from={0} overshoot={0.15} durationInFrames={14} ease="back">
        <div style={textStyle}>{text}</div>
      </ScaleIn>
    );
  } else if (animation === "word_cascade") {
    const words = text.split(/\s+/);
    inner = (
      <div style={textStyle}>
        {words.map((w, i) => (
          <SlideIn
            key={i}
            direction="up"
            delay={i * 3}
            durationInFrames={14}
            style={{ display: "inline-block", marginRight: "0.3em" }}
          >
            {w}
          </SlideIn>
        ))}
      </div>
    );
  } else if (animation === "typewriter") {
    inner = (
      <div style={textStyle}>
        <Typewriter text={text} cps={30} cursor />
      </div>
    );
  } else {
    inner = (
      <FadeIn durationInFrames={20}>
        <SlideIn direction="up" distance={40} durationInFrames={20}>
          <div style={textStyle}>{text}</div>
        </SlideIn>
      </FadeIn>
    );
  }

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        alignItems: "center",
        justifyContent: "center",
        padding: 80,
      }}
    >
      {inner}
    </AbsoluteFill>
  );
};
