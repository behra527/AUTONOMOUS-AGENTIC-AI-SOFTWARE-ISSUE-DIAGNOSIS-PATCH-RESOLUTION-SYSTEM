FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY apps/api ./apps/api
COPY alembic.ini ./
COPY examples ./examples
COPY --from=web /web/dist ./apps/web/dist
RUN useradd --uid 10001 --create-home bughound && mkdir -p /app/data && chown -R bughound:bughound /app
USER bughound
ENV PYTHONPATH=/app/apps/api
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
