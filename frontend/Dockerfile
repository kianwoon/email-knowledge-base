FROM node:18-alpine AS build

WORKDIR /app

# Copy dependency files first
COPY package*.json ./

# Install dependencies first
RUN npm install

# Then copy the rest of the application
COPY . .

# Set environment variables
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
ENV NODE_ENV=production

# Build with verbose output to see what's failing
RUN npm run build --verbose

# Production stage
FROM nginx:alpine

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
