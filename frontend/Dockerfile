# Frontend Dockerfile
FROM node:18-alpine as builder

WORKDIR /app

# Install dependencies needed for native builds
RUN apk add --no-cache python3 make g++

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev dependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Build the application (skip TypeScript check for Docker build)
ENV NODE_ENV=production
RUN npm run build:production

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Nginx runs as root in Docker containers by default
# This is safe and standard practice for containerized nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"] 