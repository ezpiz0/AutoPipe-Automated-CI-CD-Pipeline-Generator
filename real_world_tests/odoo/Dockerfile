# syntax=docker/dockerfile:1.4

FROM python:None-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --target=/app/deps -r requirements.txt
COPY . .

FROM python:None-slim
WORKDIR /app
COPY --from=builder /app/deps /usr/local/lib/pythonNone/site-packages
COPY --from=builder /app /app
# Assuming standard entrypoint, can be customized via extra_vars
CMD ["python", "main.py"]

