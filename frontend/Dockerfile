# =============================================================================
# frontend/Dockerfile
# Multi-stage build:
#   Stage 1 (builder) — installs deps + builds static files with Vite
#   Stage 2 (runner)  — tiny node image serving the /dist output with `serve`
#
# For local dev, use docker-compose "frontend-dev" service instead,
# which mounts src/ as a volume and runs `npm run dev` with HMR.
# =============================================================================

# ---- Stage 1: Build ----
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifests first for layer caching
COPY package*.json ./

# Install all dependencies (including devDependencies for the build)
RUN npm ci

# Copy source
COPY . .

# Build production bundle
RUN npm run build

# ---- Stage 2: Serve ----
FROM node:20-alpine AS runner

WORKDIR /app

# Install `serve` to render the static build output
RUN npm install -g serve

# Copy built assets from builder
COPY --from=builder /app/dist ./dist

EXPOSE 80

CMD ["serve", "-s", "dist", "-l", "80"]
