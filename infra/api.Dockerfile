FROM ghcr.io/astral-sh/uv:0.9.26 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY scripts/download-nlp-data.sh ./scripts/download-nlp-data.sh
RUN bash scripts/download-nlp-data.sh /app/.venv/bin/python /app/.nltk-data
COPY backend/homechem ./homechem
RUN useradd --system --uid 10001 homechem
USER homechem
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "homechem.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
