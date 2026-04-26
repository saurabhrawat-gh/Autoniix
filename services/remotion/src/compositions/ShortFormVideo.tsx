import React from "react";
import { z } from "zod";
import { MainVideo, mainVideoSchema, mainVideoDefaults } from "./MainVideo";

/**
 * ShortFormVideo shares the same schema as MainVideo but is rendered
 * at 1080x1920 (9:16). The direction upstream should set aspect=9:16.
 */
export const shortFormSchema = mainVideoSchema;
export type ShortFormProps = z.infer<typeof shortFormSchema>;

export const shortFormDefaults: ShortFormProps = {
  direction: {
    ...mainVideoDefaults.direction,
    meta: {
      ...mainVideoDefaults.direction.meta,
      aspect: "9:16",
      resolution: { width: 1080, height: 1920 },
    },
  },
};

export const ShortFormVideo: React.FC<ShortFormProps> = (props) => {
  return <MainVideo {...props} />;
};
