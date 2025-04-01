FROM node:18-alpine AS build

WORKDIR /app

# Debug: List contents before copying
RUN ls -la

# Copy package.json and package-lock.json first for better caching
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY . ./

# Debug: List contents after copying
RUN ls -la

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

# Debug: Create nginx config directory if it doesn't exist
RUN mkdir -p /etc/nginx/conf.d

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Debug: Verify nginx config
RUN ls -la /etc/nginx/conf.d/
RUN cat /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
