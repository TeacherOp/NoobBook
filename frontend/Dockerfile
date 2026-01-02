# Frontend Dockerfile - Multi-stage build
FROM node:22-alpine AS base

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Set working directory
WORKDIR /app

# Development stage
FROM base AS development
COPY frontend/package*.json frontend/pnpm-lock.yaml* ./
RUN pnpm install && \
    pnpm rebuild esbuild
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/tsconfig*.json ./
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# Build stage
FROM base AS builder
ARG VITE_API_URL=http://localhost:5000/api/v1
ENV VITE_API_URL=$VITE_API_URL
COPY frontend/package*.json frontend/pnpm-lock.yaml* ./
RUN pnpm install && \
    pnpm rebuild esbuild
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/tsconfig*.json ./
RUN pnpm build

# Production stage
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY scripts/docker/nginx.conf /etc/nginx/nginx.conf

# Fix nginx permissions for non-root user
RUN addgroup -g 1001 -S noobbook && \
    adduser -S noobbook -u 1001 -G noobbook && \
    chown -R noobbook:noobbook /usr/share/nginx/html && \
    chown -R noobbook:noobbook /var/cache/nginx && \
    chown -R noobbook:noobbook /var/log/nginx && \
    chown -R noobbook:noobbook /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R noobbook:noobbook /var/run/nginx.pid

USER noobbook

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
