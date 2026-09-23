FROM node:22.23.1-alpine AS base
WORKDIR /app

FROM base AS deps
RUN apk add --no-cache libc6-compat python3 make g++
COPY package.json package-lock.json .npmrc ./
COPY backend/api/streaming-hub/package.json ./backend/api/streaming-hub/
RUN npm ci --workspace=backend/api/streaming-hub --legacy-peer-deps

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json ./package.json
COPY tsconfig.base.json ./
COPY backend/api/streaming-hub ./backend/api/streaming-hub
RUN npm run build --workspace=@autoniix/streaming-hub-v2

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 fastify
COPY --from=builder --chown=fastify:nodejs /app/backend/api/streaming-hub/dist ./dist
COPY --from=builder --chown=fastify:nodejs /app/backend/api/streaming-hub/package.json ./
COPY --from=builder --chown=fastify:nodejs /app/node_modules ./node_modules
USER fastify
EXPOSE 8090
ENV PORT=8090
CMD ["node", "dist/index.js"]
