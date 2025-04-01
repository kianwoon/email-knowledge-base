FROM node:18-alpine AS build

WORKDIR /app

# Copy package.json and package-lock.json first for better caching
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY . ./

# Set environment variables
ENV TSC_COMPILE_ON_ERROR=true
ENV CI=false
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add nginx configuration to handle client-side routing
RUN echo 'location / { \
    root /usr/share/nginx/html; \
    try_files $uri $uri/ /index.html; \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

# Update nginx to listen on port 3000
RUN sed -i 's/listen\s*80;/listen 3000;/g' /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]
