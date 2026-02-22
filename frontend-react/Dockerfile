# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty VITE_API_HOST makes the frontend use same-origin requests,
# which nginx will proxy to the backend container.
ENV VITE_API_HOST=""
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
