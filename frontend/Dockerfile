FROM node:20 AS build

# 构建期 npm 源，可通过 docker compose build args 覆盖（国内建议用镜像源）
ARG NPM_REGISTRY=https://registry.npmjs.org

WORKDIR /app

COPY package*.json ./
RUN npm config set registry "$NPM_REGISTRY" && npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
