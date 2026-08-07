# Motor de padrões — serviço HTTP (FastAPI :1841).
#
# NÃO instala o pacote `MetaTrader5`: ele é Windows-only e conversa com o terminal por
# IPC. O coletor que fala com o MT5 roda no HOST, não aqui. Este container faz o resto —
# detecção, confluência, decisão, backtest — lendo os candles do Postgres.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    EM_CONTAINER=1

WORKDIR /app

# Camada de dependências separada do código: editar um detector não reinstala o numpy.
COPY pyproject.toml ./
COPY trader_ai/__init__.py ./trader_ai/
RUN pip install --no-cache-dir ".[servico]"

COPY trader_ai/ ./trader_ai/
COPY scripts/ ./scripts/

# Usuário sem privilégio — o serviço não escreve nada no filesystem.
RUN useradd --create-home --uid 1001 motor && chown -R motor:motor /app
USER motor

EXPOSE 1841

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1841/saude', timeout=4)"

CMD ["uvicorn", "trader_ai.servico:app", "--host", "0.0.0.0", "--port", "1841"]
