import React from "react";
import { LogoBug, type BugCorner, type LogoBugProps } from "../overlays/LogoBug";

/**
 * Branding alias around LogoBug with opinionated defaults for always-on
 * channel watermarking. Kept as its own component so presets are clearly
 * separated from ad-hoc `ov.watermark.*` usages.
 */
export interface ChannelWatermarkProps extends Omit<LogoBugProps, "corner"> {
  corner?: BugCorner;
}

export const ChannelWatermark: React.FC<ChannelWatermarkProps> = ({
  corner = "tr",
  heightPx = 70,
  opacity = 0.85,
  padding = 56,
  ...rest
}) => <LogoBug corner={corner} heightPx={heightPx} opacity={opacity} padding={padding} {...rest} />;
