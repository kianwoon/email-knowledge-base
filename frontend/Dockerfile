# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files and install
COPY frontend/package*.json ./
RUN npm install

# Copy source files
COPY frontend/ ./

# Set build-time ENV variables to placeholders
# These literal strings will be baked into the JS files by Vite
ENV VITE_API_BASE_URL="__VITE_API_BASE_URL_PLACEHOLDER__"
ENV VITE_WEBSOCKET_URL="__VITE_WEBSOCKET_URL_PLACEHOLDER__"

# Set optional build flags (keep these if needed)
ENV TSC_COMPILE_ON_ERROR=true
ENV CI=false

# Skip TypeScript checks if needed (keep if needed)
RUN sed -i 's/tsc && vite build/vite build/g' package.json

# Build the frontend with placeholders
RUN npm run build

# -------------------
# Production stage
# -------------------
FROM nginx:alpine

# Install sed (stream editor for replacing text)
RUN apk add --no-cache sed

# Define where the built files are and where nginx serves from
ARG BUILT_ASSETS_DIR=/app/dist
ARG NGINX_ROOT_DIR=/usr/share/nginx/html

# Copy built static files from the build stage
COPY --from=build ${BUILT_ASSETS_DIR} ${NGINX_ROOT_DIR}

# Copy the custom Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy the entrypoint script that will substitute variables
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

# Set the entrypoint script to run when the container starts
ENTRYPOINT ["/docker-entrypoint.sh"]

# Tell Nginx to run in the foreground (managed by the entrypoint script)
CMD ["nginx", "-g", "daemon off;"]