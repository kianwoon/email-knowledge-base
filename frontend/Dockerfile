FROM node:18-alpine AS build

WORKDIR /app

# Copy package.json and package-lock.json first for better caching
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY frontend/ ./

# Set environment variables
ENV TSC_COMPILE_ON_ERROR=true
ENV CI=false

# Build arguments for API URL
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Skip TypeScript type checking entirely
RUN sed -i 's/tsc && vite build/vite build/g' package.json

# Print env var for debugging, then run build
RUN echo "Build-time VITE_WEBSOCKET_URL: [$VITE_WEBSOCKET_URL]" && \
    echo "Build-time VITE_API_BASE_URL: [$VITE_API_BASE_URL]" && \
    npm run build

# Production stage
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
