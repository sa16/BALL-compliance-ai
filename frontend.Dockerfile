# frontend.Dockerfile

# --- Stage 1: Build the React App ---
FROM node:18-alpine as builder
WORKDIR /app

# Copy package.json and lockfile from the frontend directory
COPY ball-frontend/package.json ball-frontend/package-lock.json ./

# Install npm dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY ball-frontend/ ./

# Build for Production (Creates the /dist folder)
RUN npm run build

# --- Stage 2: Serve with Nginx ---
FROM nginx:alpine

# Copy the build output from Stage 1 to Nginx's html folder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy our custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 755 means: Owner can Write, Everyone can Read/Execute.
RUN chmod -R 755 /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]