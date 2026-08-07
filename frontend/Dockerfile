# Tela do cronos-trader (:5180).
#
# Build estático servido por nginx, que também faz o proxy de /api e /ws para o backend.
# É o mesmo arranjo do `vite dev`: o navegador fala com uma origem só, então não há CORS
# nem URL diferente entre desenvolvimento e produção.

# --- build -------------------------------------------------------------------
FROM node:20-slim AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

# --- runtime -----------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=4s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
