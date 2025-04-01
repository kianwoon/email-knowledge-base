FROM node:18 AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with clean npm cache and install
RUN npm cache clean --force && \
    npm install --no-optional --production=false

# Copy source files
COPY . .

# Set memory limits and environment variables
ENV NODE_OPTIONS="--max-old-space-size=2048"
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
ENV NODE_ENV=production

# Attempt build with error logging
RUN set -x && \
    npm run build > build.log 2>&1 || (cat build.log && exit 1)

# Production stage
FROM nginx:stable-alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Configure nginx
RUN echo 'server { \n\
    listen 80; \n\
    root /usr/share/nginx/html; \n\
    location / { \n\
        try_files $uri $uri/ /index.html; \n\
    } \n\
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
