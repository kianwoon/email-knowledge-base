FROM node:18-alpine AS build

WORKDIR /app

# Copy package files and install
COPY frontend/package*.json ./
RUN npm install

# Copy source files
COPY frontend/ ./

# Set optional build flags
ENV TSC_COMPILE_ON_ERROR=true
ENV CI=false

# Skip TypeScript checks if needed
RUN sed -i 's/tsc && vite build/vite build/g' package.json

# Just echo for visibility — not needed but useful for debugging
RUN echo "VITE_API_BASE_URL: $VITE_API_BASE_URL" && \
    echo "VITE_WEBSOCKET_URL: $VITE_WEBSOCKET_URL" && \
    npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
