import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { easings } from "../../utils/easing";

export interface TimelineEvent {
  label: string;
  date: string;
  description?: string;
  color?: string;
}

export interface TimelineAnimationProps {
  title?: string;
  events: TimelineEvent[];
  orientation?: "horizontal" | "vertical";
  bg?: string;
  color?: string;
  accent?: string;
}

const PALETTE = ["#FFD60A", "#FF3B30", "#00E0FF", "#30D158", "#BF5AF2", "#FF9F0A"];

export const TimelineAnimation: React.FC<TimelineAnimationProps> = ({
  title,
  events,
  orientation = "horizontal",
  bg = "#0A0A0A",
  color = "#FFFFFF",
  accent = "#FFD60A",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const n = events.length;
  const perEvent = Math.max(12, Math.floor((durationInFrames - 20) / Math.max(1, n)));

  const spineP = easings.power2(
    interpolate(frame, [10, 10 + perEvent * n], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  if (orientation === "horizontal") {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: bg,
          padding: 100,
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        {title && (
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 900,
              fontSize: 72,
              color,
              marginBottom: 80,
              letterSpacing: -1,
            }}
          >
            {title}
          </div>
        )}
        <div style={{ position: "relative", height: 300 }}>
          {/* spine */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: 0,
              height: 4,
              background: accent,
              width: `${spineP * 100}%`,
              transform: "translateY(-50%)",
              boxShadow: `0 0 20px ${accent}80`,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: 0,
              right: 0,
              height: 4,
              background: "rgba(255,255,255,0.1)",
              transform: "translateY(-50%)",
              zIndex: -1,
            }}
          />
          {events.map((e, i) => {
            const eventStart = 10 + i * perEvent;
            const eventP = interpolate(frame, [eventStart, eventStart + 14], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const col = e.color ?? PALETTE[i % PALETTE.length];
            const xPct = ((i + 0.5) / n) * 100;
            const above = i % 2 === 0;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${xPct}%`,
                  top: "50%",
                  transform: `translate(-50%, -50%) scale(${eventP})`,
                  opacity: eventP,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: col,
                    boxShadow: `0 0 30px ${col}`,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "50%",
                    [above ? "bottom" : "top"]: 48,
                    transform: "translateX(-50%)",
                    width: 240,
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontFamily: "Inter, sans-serif",
                      fontWeight: 900,
                      fontSize: 22,
                      color: col,
                      letterSpacing: 2,
                    }}
                  >
                    {e.date}
                  </div>
                  <div
                    style={{
                      fontFamily: "Inter, sans-serif",
                      fontWeight: 700,
                      fontSize: 26,
                      color,
                      marginTop: 4,
                    }}
                  >
                    {e.label}
                  </div>
                  {e.description && (
                    <div
                      style={{
                        fontFamily: "Inter, sans-serif",
                        fontWeight: 400,
                        fontSize: 18,
                        color,
                        opacity: 0.7,
                        marginTop: 4,
                      }}
                    >
                      {e.description}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: bg, padding: 80 }}>
      {title && (
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontWeight: 900,
            fontSize: 64,
            color,
            marginBottom: 40,
          }}
        >
          {title}
        </div>
      )}
      <div style={{ position: "relative", flex: 1, paddingLeft: 60 }}>
        <div
          style={{
            position: "absolute",
            left: 20,
            top: 0,
            width: 4,
            height: `${spineP * 100}%`,
            background: accent,
            boxShadow: `0 0 20px ${accent}80`,
          }}
        />
        {events.map((e, i) => {
          const eventStart = 10 + i * perEvent;
          const eventP = interpolate(frame, [eventStart, eventStart + 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const col = e.color ?? PALETTE[i % PALETTE.length];
          return (
            <div
              key={i}
              style={{
                position: "relative",
                marginBottom: 40,
                opacity: eventP,
                transform: `translateX(${(1 - eventP) * 40}px)`,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: -50,
                  top: 8,
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  background: col,
                  boxShadow: `0 0 24px ${col}`,
                }}
              />
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 900,
                  fontSize: 22,
                  color: col,
                  letterSpacing: 2,
                }}
              >
                {e.date}
              </div>
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 700,
                  fontSize: 32,
                  color,
                }}
              >
                {e.label}
              </div>
              {e.description && (
                <div
                  style={{
                    fontFamily: "Inter, sans-serif",
                    fontSize: 22,
                    color,
                    opacity: 0.7,
                    marginTop: 4,
                  }}
                >
                  {e.description}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
