import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setConcurrency(Number(process.env.REMOTION_CONCURRENCY ?? 1));
Config.setChromiumOpenGlRenderer("angle");
Config.setOverwriteOutput(true);

Config.overrideWebpackConfig((currentConfiguration) => {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const webpack = require("webpack");
  return {
    ...currentConfiguration,
    plugins: [
      ...(currentConfiguration.plugins ?? []),
      // Strip the "node:" URI prefix from built-in module imports.
      // Packages like nanoid v5 and undici use `import ... from "node:crypto"`
      // which webpack does not handle natively — this replacement makes them
      // resolve to the standard (non-prefixed) built-in equivalents.
      new webpack.NormalModuleReplacementPlugin(
        /^node:/,
        (resource: { request: string }) => {
          resource.request = resource.request.replace(/^node:/, "");
        }
      ),
    ],
  };
});
