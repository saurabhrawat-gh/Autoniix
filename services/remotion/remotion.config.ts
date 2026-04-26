import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setConcurrency(Number(process.env.REMOTION_CONCURRENCY ?? 1));
Config.setChromiumOpenGlRenderer("angle");
Config.setOverwriteOutput(true);
