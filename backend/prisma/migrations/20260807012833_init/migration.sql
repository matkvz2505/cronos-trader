-- CreateEnum
CREATE TYPE "Papel" AS ENUM ('USUARIO', 'ADMIN');

-- CreateEnum
CREATE TYPE "Direcao" AS ENUM ('ALTA', 'BAIXA');

-- CreateEnum
CREATE TYPE "StatusSinal" AS ENUM ('ABERTO', 'ACIONADO', 'ALVO', 'STOP', 'EXPIRADO', 'CANCELADO');

-- CreateTable
CREATE TABLE "usuarios" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "senhaHash" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "papel" "Papel" NOT NULL DEFAULT 'USUARIO',
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "capital" DECIMAL(14,2) NOT NULL DEFAULT 10000,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ultimoLogin" TIMESTAMP(3),

    CONSTRAINT "usuarios_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessoes" (
    "id" TEXT NOT NULL,
    "usuarioId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "expiraEm" TIMESTAMP(3) NOT NULL,
    "revogadaEm" TIMESTAMP(3),
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userAgent" TEXT,

    CONSTRAINT "sessoes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "candles" (
    "ativo" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "ts" TIMESTAMP(3) NOT NULL,
    "abertura" DECIMAL(14,2) NOT NULL,
    "maxima" DECIMAL(14,2) NOT NULL,
    "minima" DECIMAL(14,2) NOT NULL,
    "fechamento" DECIMAL(14,2) NOT NULL,
    "volume" DECIMAL(16,2) NOT NULL DEFAULT 0,

    CONSTRAINT "candles_pkey" PRIMARY KEY ("ativo","timeframe","ts")
);

-- CreateTable
CREATE TABLE "sinais" (
    "id" TEXT NOT NULL,
    "ativo" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "ts" TIMESTAMP(3) NOT NULL,
    "direcao" "Direcao" NOT NULL,
    "padraoId" TEXT NOT NULL,
    "padraoNome" TEXT NOT NULL,
    "entrada" DECIMAL(14,2) NOT NULL,
    "stop" DECIMAL(14,2) NOT NULL,
    "alvo" DECIMAL(14,2) NOT NULL,
    "origemAlvo" TEXT NOT NULL,
    "riscoPontos" DECIMAL(14,2) NOT NULL,
    "retornoPontos" DECIMAL(14,2) NOT NULL,
    "rr" DECIMAL(6,2) NOT NULL,
    "contratos" INTEGER NOT NULL,
    "score" DECIMAL(5,4) NOT NULL,
    "confiabilidade" DECIMAL(5,4) NOT NULL,
    "fatores" JSONB NOT NULL,
    "observacoes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "zonaQuente" BOOLEAN NOT NULL DEFAULT false,
    "viesMtf" TEXT,
    "status" "StatusSinal" NOT NULL DEFAULT 'ABERTO',
    "precoSaida" DECIMAL(14,2),
    "resultadoPontos" DECIMAL(14,2),
    "fechadoEm" TIMESTAMP(3),
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sinais_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "deteccoes" (
    "id" TEXT NOT NULL,
    "ativo" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "ts" TIMESTAMP(3) NOT NULL,
    "padraoId" TEXT NOT NULL,
    "padraoNome" TEXT NOT NULL,
    "direcao" TEXT NOT NULL,
    "forca" DECIMAL(5,4) NOT NULL,
    "scoreBruto" DECIMAL(5,4) NOT NULL,

    CONSTRAINT "deteccoes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "execucoes_backtest" (
    "id" TEXT NOT NULL,
    "ativo" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "inicio" TIMESTAMP(3) NOT NULL,
    "fim" TIMESTAMP(3) NOT NULL,
    "capital" DECIMAL(14,2) NOT NULL,
    "modo" TEXT NOT NULL DEFAULT 'backtest',
    "sinaisGerados" INTEGER NOT NULL,
    "acionados" INTEGER NOT NULL,
    "taxaAcerto" DECIMAL(5,4) NOT NULL,
    "expectanciaR" DECIMAL(6,3) NOT NULL,
    "resultadoReais" DECIMAL(14,2) NOT NULL,
    "rebaixamentoMax" DECIMAL(14,2) NOT NULL,
    "porPadrao" JSONB NOT NULL,
    "porJanela" JSONB NOT NULL,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "execucoes_backtest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "calibracoes_padrao" (
    "padraoId" TEXT NOT NULL,
    "ativo" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "taxaAcerto" DECIMAL(5,4) NOT NULL,
    "expectanciaR" DECIMAL(6,3) NOT NULL,
    "ocorrencias" INTEGER NOT NULL,
    "suficiente" BOOLEAN NOT NULL DEFAULT false,
    "atualizadoEm" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "calibracoes_padrao_pkey" PRIMARY KEY ("padraoId","ativo","timeframe")
);

-- CreateTable
CREATE TABLE "anotacoes_sinal" (
    "id" TEXT NOT NULL,
    "sinalId" TEXT NOT NULL,
    "usuarioId" TEXT NOT NULL,
    "operou" BOOLEAN NOT NULL DEFAULT false,
    "texto" TEXT,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "anotacoes_sinal_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "usuarios_email_key" ON "usuarios"("email");

-- CreateIndex
CREATE UNIQUE INDEX "sessoes_tokenHash_key" ON "sessoes"("tokenHash");

-- CreateIndex
CREATE INDEX "sessoes_usuarioId_idx" ON "sessoes"("usuarioId");

-- CreateIndex
CREATE INDEX "candles_ativo_timeframe_ts_idx" ON "candles"("ativo", "timeframe", "ts" DESC);

-- CreateIndex
CREATE INDEX "sinais_status_ts_idx" ON "sinais"("status", "ts" DESC);

-- CreateIndex
CREATE INDEX "sinais_ativo_ts_idx" ON "sinais"("ativo", "ts" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "sinais_ativo_timeframe_ts_padraoId_key" ON "sinais"("ativo", "timeframe", "ts", "padraoId");

-- CreateIndex
CREATE INDEX "deteccoes_ativo_timeframe_ts_idx" ON "deteccoes"("ativo", "timeframe", "ts" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "deteccoes_ativo_timeframe_ts_padraoId_key" ON "deteccoes"("ativo", "timeframe", "ts", "padraoId");

-- CreateIndex
CREATE INDEX "execucoes_backtest_ativo_criadoEm_idx" ON "execucoes_backtest"("ativo", "criadoEm" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "anotacoes_sinal_sinalId_usuarioId_key" ON "anotacoes_sinal"("sinalId", "usuarioId");

-- AddForeignKey
ALTER TABLE "sessoes" ADD CONSTRAINT "sessoes_usuarioId_fkey" FOREIGN KEY ("usuarioId") REFERENCES "usuarios"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "anotacoes_sinal" ADD CONSTRAINT "anotacoes_sinal_sinalId_fkey" FOREIGN KEY ("sinalId") REFERENCES "sinais"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "anotacoes_sinal" ADD CONSTRAINT "anotacoes_sinal_usuarioId_fkey" FOREIGN KEY ("usuarioId") REFERENCES "usuarios"("id") ON DELETE CASCADE ON UPDATE CASCADE;
