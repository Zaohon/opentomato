ARG NODE_IMAGE=node:20-alpine
ARG NGINX_IMAGE=nginx:1.27-alpine

FROM ${NODE_IMAGE} AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ${NGINX_IMAGE}
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default-http.conf
COPY nginx.ssl.conf /etc/nginx/templates/default-ssl.conf
COPY docker-entrypoint.d/40-select-default-conf.sh /docker-entrypoint.d/40-select-default-conf.sh
RUN chmod +x /docker-entrypoint.d/40-select-default-conf.sh
EXPOSE 80 443
