# Pinned via versions.env NODE_ALPINE_IMAGE=node:20.18.0-alpine
ARG NODE_ALPINE_IMAGE=node:20.18.0-alpine
FROM ${NODE_ALPINE_IMAGE} AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_WS_URL=ws://localhost:8020
ENV API_INTERNAL_URL=http://dashboard-bff:8020
RUN npm run build

FROM ${NODE_ALPINE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost:3000 || exit 1
CMD ["node", "server.js"]
