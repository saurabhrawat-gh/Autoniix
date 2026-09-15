import React from "react";
import { Composition } from "remotion";
import { initAssetRegistries } from "./registry";
import { loadFonts } from "./utils/fonts";
import { MainVideo, mainVideoSchema, mainVideoDefaults } from "./compositions/MainVideo";
import { ShortFormVideo, shortFormSchema, shortFormDefaults } from "./compositions/ShortFormVideo";
import { ThumbnailComp, thumbnailSchema, thumbnailDefaults } from "./compositions/ThumbnailComp";

initAssetRegistries();
loadFonts();

const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MainVideo"
        component={MainVideo}
        durationInFrames={FPS * 10}
        fps={FPS}
        width={1920}
        height={1080}
        schema={mainVideoSchema}
        defaultProps={mainVideoDefaults}
        calculateMetadata={({ props }) => {
          const d = props.direction;
          const totalMs =
            d?.segments?.reduce((a: number, s: { duration_ms: number }) => a + s.duration_ms, 0) ??
            0;
          const fps = d?.meta?.fps ?? FPS;
          const w = d?.meta?.resolution?.width ?? 1920;
          const h = d?.meta?.resolution?.height ?? 1080;
          const frames = Math.max(fps, Math.round((totalMs / 1000) * fps));
          return { durationInFrames: frames, fps, width: w, height: h };
        }}
      />

      <Composition
        id="ShortFormVideo"
        component={ShortFormVideo}
        durationInFrames={FPS * 10}
        fps={FPS}
        width={1080}
        height={1920}
        schema={shortFormSchema}
        defaultProps={shortFormDefaults}
        calculateMetadata={({ props }) => {
          const d = props.direction;
          const totalMs =
            d?.segments?.reduce((a: number, s: { duration_ms: number }) => a + s.duration_ms, 0) ??
            0;
          const fps = d?.meta?.fps ?? FPS;
          const w = d?.meta?.resolution?.width ?? 1080;
          const h = d?.meta?.resolution?.height ?? 1920;
          const frames = Math.max(fps, Math.round((totalMs / 1000) * fps));
          return { durationInFrames: frames, fps, width: w, height: h };
        }}
      />

      <Composition
        id="ThumbnailComp"
        component={ThumbnailComp}
        durationInFrames={1}
        fps={FPS}
        width={1280}
        height={720}
        schema={thumbnailSchema}
        defaultProps={thumbnailDefaults}
      />
    </>
  );
};
