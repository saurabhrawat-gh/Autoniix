FROM node:22.23.1-alpine AS base

WORKDIR /app

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat python3 make g++

COPY package.json package-lock.json .npmrc ./
COPY shared/ts/contracts/package.json ./shared/ts/contracts/
COPY backend/api/gateway/package.json ./backend/api/gateway/

RUN npm ci --workspace=backend/api/gateway

# Build the application
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json ./package.json

COPY tsconfig.base.json ./
COPY shared/ts/contracts ./shared/ts/contracts
COPY backend/api/gateway ./backend/api/gateway

# Build contracts first
RUN npm run build --workspace=@autoniix/contracts

# Build gateway
RUN npm run build --workspace=@autoniix/gateway-v2

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 fastify

COPY --from=builder --chown=fastify:nodejs /app/backend/api/gateway/dist ./dist
COPY --from=builder --chown=fastify:nodejs /app/backend/api/gateway/package.json ./
COPY --from=builder --chown=fastify:nodejs /app/node_modules ./node_modules

USER fastify

EXPOSE 8080

ENV PORT=8080

CMD ["node", "dist/index.js"]
