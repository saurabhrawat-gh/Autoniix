import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";

export const thumbnailSchema = z.object({
  layout_preset: z.string().default("thumb.text_left_image_right"),
  background_url: z.string().url().optional(),
  title: z
    .object({
      text: z.string(),
      font: z.string().default("Inter"),
      weight: z.number().default(900),
      size: z.number().default(120),
      color: z.string().default("#FFFFFF"),
      stroke: z.object({ color: z.string(), width: z.number() }).optional(),
    })
    .default({ text: "PREVIEW", font: "Inter", weight: 900, size: 120, color: "#FFFFFF" }),
  accent_color: z.string().default("#FF3B30"),
});

export type ThumbnailProps = z.infer<typeof thumbnailSchema>;

export const thumbnailDefaults: ThumbnailProps = {
  layout_preset: "thumb.text_left_image_right",
  title: { text: "PREVIEW", font: "Inter", weight: 900, size: 120, color: "#FFFFFF" },
  accent_color: "#FF3B30",
};

export const ThumbnailComp: React.FC<ThumbnailProps> = ({
  background_url,
  title,
  accent_color,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0A0A0A" }}>
      {background_url && (
        <AbsoluteFill>
          <Img
            src={background_url}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          <AbsoluteFill style={{ backgroundColor: "rgba(0,0,0,0.35)" }} />
        </AbsoluteFill>
      )}
      <AbsoluteFill
        style={{
          padding: 80,
          justifyContent: "center",
          alignItems: "flex-start",
        }}
      >
        <div
          style={{
            borderLeft: `12px solid ${accent_color}`,
            paddingLeft: 32,
            fontFamily: title.font,
            fontWeight: title.weight,
            fontSize: title.size,
            color: title.color,
            lineHeight: 1.05,
            letterSpacing: -2,
            textShadow: title.stroke
              ? `0 0 ${title.stroke.width}px ${title.stroke.color}`
              : undefined,
            WebkitTextStroke: title.stroke
              ? `${title.stroke.width}px ${title.stroke.color}`
              : undefined,
            maxWidth: "85%",
          }}
        >
          {title.text}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
