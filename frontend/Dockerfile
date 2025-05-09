# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files and install
COPY frontend/package*.json ./
# NOTE: Keep the original "build" script (including "tsc") in package.json to ensure TypeScript compilation before Vite bundling.

# Install dependencies reproducibly
RUN npm ci

# Copy source files

COPY frontend/ ./
# Strip potential BOM or stray characters from mcpClient.ts to fix parse errors
RUN sed -i '1s/^\xEF\xBB\xBF//' src/api/mcpClient.ts || true

# --- Hardcode Production URLs for the Build ---
# Use the combined path needed for Koyeb routing (/api) + FastAPI prefix (/api/v1)
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api/v1
ENV VITE_WEBSOCKET_URL=wss://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api/v1/ws/analysis
ENV MCP_SERVER=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/invoke/

# Set optional build flags (if needed)
ENV TSC_COMPILE_ON_ERROR=true
ENV CI=false

# Build the frontend - URLs are now baked in
RUN npm run build

# -------------------
# Production stage (Simpler Nginx)
# -------------------
FROM nginx:alpine

# Define where the built files are and where nginx serves from
ARG BUILT_ASSETS_DIR=/app/dist
ARG NGINX_ROOT_DIR=/usr/share/nginx/html

# Copy built static files from the build stage
COPY --from=build ${BUILT_ASSETS_DIR} ${NGINX_ROOT_DIR}

# Copy the custom Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Start Nginx directly
CMD ["nginx", "-g", "daemon off;"]