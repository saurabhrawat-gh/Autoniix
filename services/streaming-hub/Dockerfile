FROM node:22.23.1-alpine AS base
WORKDIR /app

FROM base AS deps
RUN apk add --no-cache libc6-compat python3 make g++
COPY package.json package-lock.json ./
COPY services/streaming-hub-v2/package.json ./services/streaming-hub-v2/
RUN npm ci --workspace=services/streaming-hub-v2 --legacy-peer-deps

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/services/streaming-hub-v2/node_modules ./services/streaming-hub-v2/node_modules
COPY tsconfig.base.json ./
COPY services/streaming-hub-v2 ./services/streaming-hub-v2
RUN npm run build --workspace=@autoniix/streaming-hub-v2

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 fastify
COPY --from=builder --chown=fastify:nodejs /app/services/streaming-hub-v2/dist ./dist
COPY --from=builder --chown=fastify:nodejs /app/services/streaming-hub-v2/package.json ./
COPY --from=builder --chown=fastify:nodejs /app/node_modules ./node_modules
USER fastify
EXPOSE 8090
ENV PORT=8090
CMD ["node", "dist/index.js"]
