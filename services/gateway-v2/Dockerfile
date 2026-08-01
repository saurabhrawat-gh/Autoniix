FROM node:22.23.1-alpine AS base

WORKDIR /app

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat python3 make g++

COPY package.json package-lock.json ./
COPY libs/ts/contracts/package.json ./libs/ts/contracts/
COPY services/gateway-v2/package.json ./services/gateway-v2/

RUN npm ci --workspace=services/gateway-v2

# Build the application
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/services/gateway-v2/node_modules ./services/gateway-v2/node_modules
COPY --from=deps /app/libs/ts/contracts/node_modules ./libs/ts/contracts/node_modules

COPY tsconfig.base.json ./
COPY libs/ts/contracts ./libs/ts/contracts
COPY services/gateway-v2 ./services/gateway-v2

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

COPY --from=builder --chown=fastify:nodejs /app/services/gateway-v2/dist ./dist
COPY --from=builder --chown=fastify:nodejs /app/services/gateway-v2/package.json ./
COPY --from=builder --chown=fastify:nodejs /app/node_modules ./node_modules

USER fastify

EXPOSE 8080

ENV PORT=8080

CMD ["node", "dist/index.js"]
