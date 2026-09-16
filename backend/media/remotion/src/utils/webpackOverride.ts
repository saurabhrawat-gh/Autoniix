/**
 * Shared webpack override applied to BOTH:
 *   - remotion.config.ts  (CLI: remotion studio / remotion bundle)
 *   - bundleCache.ts      (programmatic: bundle() called by the worker)
 *
 * nanoid v5 and undici v6 use `import ... from "node:crypto"` (and other
 * node: scheme specifiers). Webpack does not handle the "node:" URI prefix
 * natively and throws UnhandledSchemeError. The NormalModuleReplacementPlugin
 * strips the prefix so webpack resolves them as standard Node built-ins.
 */
import { WebpackOverrideFn } from "@remotion/bundler";

export const nodePrefixWebpackOverride: WebpackOverrideFn = (currentConfiguration) => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const webpack = require("webpack");
  return {
    ...currentConfiguration,
    resolve: {
      ...currentConfiguration.resolve,
      fallback: {
        ...((currentConfiguration.resolve?.fallback as Record<string, unknown>) ?? {}),
        crypto: false,
        stream: false,
        path: false,
        fs: false,
        os: false,
        util: false,
        buffer: false,
        url: false,
        events: false,
        assert: false,
        http: false,
        https: false,
        net: false,
        tls: false,
        zlib: false,
      },
    },
    plugins: [
      ...(currentConfiguration.plugins ?? []),
      new webpack.NormalModuleReplacementPlugin(/^node:/, (resource: { request: string }) => {
        resource.request = resource.request.replace(/^node:/, "");
      }),
    ],
  };
};
