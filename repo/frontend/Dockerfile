# frontend/Dockerfile
# Multi-stage build:
#   dev        — Vite dev server (hot reload, for local development)
#   build      — production asset compilation
#   production — Nginx serving built static files (Phase 9.5)

# ── Development stage ─────────────────────────────────────────────────────────
FROM node:20-alpine AS dev

WORKDIR /app

# Copy manifests first for layer caching
COPY package*.json ./
RUN npm install

# Source mounted as volume in docker-compose (live reload)
COPY . .

EXPOSE 5173

# Bind to 0.0.0.0 so Docker port mapping reaches the host
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]


# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build


# ── Production stage ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Remove default nginx page
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config: serve SPA with fallback to index.html for client-side routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
