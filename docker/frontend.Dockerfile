ARG NODE_VERSION=22.13.1

FROM node:${NODE_VERSION}-alpine3.21 AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# ------------------------------------------------------------------
# Development target (hot reload via bind mount)
# ------------------------------------------------------------------
FROM base AS dev
COPY frontend/ /app/
RUN if [ ! -d node_modules ]; then npm install --no-audit --no-fund; fi
EXPOSE 3000
HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]
CMD ["npm", "run", "dev"]

# ------------------------------------------------------------------
# Build target
# ------------------------------------------------------------------
FROM base AS build
COPY frontend/package.json frontend/package-lock.json* /app/
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY frontend/ /app/
ENV NODE_ENV=production
RUN npm run build

# ------------------------------------------------------------------
# Production target (minimal Next.js standalone, non-root user, tini init)
# ------------------------------------------------------------------
FROM base AS prod
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN apk add --no-cache tini \
    && addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 --ingroup nodejs nextjs

COPY --from=build --chown=10001:10001 /app/public ./public
COPY --from=build --chown=10001:10001 /app/.next/standalone ./
COPY --from=build --chown=10001:10001 /app/.next/static ./.next/static

USER 10001:10001
EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
