# Pinned via versions.env NODE_IMAGE=node:20.18.0-bookworm-slim
ARG NODE_IMAGE=node:20.18.0-bookworm-slim

# build stage
FROM ${NODE_IMAGE} AS build
WORKDIR /app

# Remotion/Chromium deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    wget \
    xdg-utils \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run typecheck

# runtime stage
FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production

# Re-install runtime system deps (Chromium + ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libgcc1 \
    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 \
    libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 lsb-release \
    wget xdg-utils ffmpeg tini \
 && rm -rf /var/lib/apt/lists/*

COPY --from=build /app /app
RUN mkdir -p /app/tmp

EXPOSE 4000
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default to API; docker-compose overrides for worker.
CMD ["npm", "run", "start:api"]
