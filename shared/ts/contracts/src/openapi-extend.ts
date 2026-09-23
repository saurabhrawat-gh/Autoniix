// Must be imported before any schema module. zod 4 builds classes through
// `$constructor` traits, so the `.openapi()` extension only reaches schemas
// created after `extendZodWithOpenApi` has run. ESM evaluates imports in
// order, so `generate-openapi.ts` imports this file first.
import { extendZodWithOpenApi } from "@asteasolutions/zod-to-openapi";
import { z } from "zod";

extendZodWithOpenApi(z);
