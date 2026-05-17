import { Config } from "@remotion/cli/config";
import { nodePrefixWebpackOverride } from "./src/utils/webpackOverride";

Config.setVideoImageFormat("jpeg");
Config.setConcurrency(Number(process.env.REMOTION_CONCURRENCY ?? 1));
Config.setChromiumOpenGlRenderer("angle");
Config.setOverwriteOutput(true);

Config.overrideWebpackConfig(nodePrefixWebpackOverride);
