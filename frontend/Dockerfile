FROM node:18-alpine AS build

WORKDIR /app

# Copy package files first
COPY package*.json ./

# Install dependencies with legacy peer deps to match local environment
RUN npm install --legacy-peer-deps

# Copy the rest of the files
COPY . .

# Set environment variables
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
ENV NODE_ENV=production
ENV CI=false

# Build the application with increased memory
RUN NODE_OPTIONS="--max-old-space-size=4096" npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Configure nginx
RUN echo 'server { \n\
    listen 80; \n\
    location / { \n\
        root /usr/share/nginx/html; \n\
        try_files $uri $uri/ /index.html; \n\
        add_header Cache-Control "no-cache"; \n\
    } \n\
}' > /etc/nginx/conf.d/default.conf

# Test nginx config
RUN nginx -t

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
