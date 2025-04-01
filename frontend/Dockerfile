FROM node:18-alpine AS build

WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN npm install

# Set environment variables
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
ENV NODE_ENV=production
ENV SKIP_TYPESCRIPT=true

# Build the application (skip TypeScript checks)
RUN npm run build -- --skipLibCheck

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
