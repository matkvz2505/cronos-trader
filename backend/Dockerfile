# API do cronos-trader (:1840).
#
# Debian slim em vez de Alpine: o Prisma precisa de binários de engine compatíveis com a
# libc do sistema, e a combinação musl + OpenSSL é a fonte clássica de
# "Query engine binary not found" em produção. Debian evita o problema inteiro.

# --- build -------------------------------------------------------------------
FROM node:20-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund

# `prisma generate` antes do build: o tsup precisa dos tipos do client gerado.
COPY prisma ./prisma
RUN npx prisma generate

COPY tsconfig.json ./
COPY src ./src
RUN npx tsc --noEmit && npx tsup src/server.ts --format esm --target node20 --clean

# --- runtime -----------------------------------------------------------------
FROM node:20-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production
WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force

# O client gerado vem do estágio de build junto com os engines nativos.
COPY --from=build /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=build /app/node_modules/@prisma/client ./node_modules/@prisma/client
COPY --from=build /app/dist ./dist
COPY prisma ./prisma

USER node

EXPOSE 1840

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:1840/api/v1').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "dist/server.js"]
