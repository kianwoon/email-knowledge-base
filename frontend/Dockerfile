FROM node:18-alpine AS build

WORKDIR /app

# Copy package files first
COPY package*.json ./

# Debug: List contents
RUN ls -la

# Install dependencies
RUN npm install

# Debug: List node_modules
RUN ls -la node_modules

# Copy source files
COPY . .

# Debug: List all files
RUN ls -la

# Set environment variables
ENV VITE_API_BASE_URL=https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
ENV NODE_ENV=production

# Debug: Print TypeScript version
RUN npx tsc --version

# Build with debug output
RUN npm run build || (echo "Build failed" && npm run build --verbose)

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
