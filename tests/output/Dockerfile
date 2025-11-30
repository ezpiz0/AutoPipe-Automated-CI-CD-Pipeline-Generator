# syntax=docker/dockerfile:1.4

FROM python:3.9-slim AS builder
WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry poetry config virtualenvs.in-project true && poetry install --no-dev
COPY . .

FROM python:3.9-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
# Assuming standard entrypoint, can be customized via extra_vars
CMD ["python", "main.py"]

