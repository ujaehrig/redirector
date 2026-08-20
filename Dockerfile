FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable

RUN python -c \
    "import tomllib; \
     v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; \
     print(v)" > /app/.version


FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.version /app/.version

ENV PATH="/app/.venv/bin:$PATH"
ENV SQLITE_PATH=/data/redirects.db
ENV PORT=8080
ENV APP_VERSION_FILE=/app/.version

LABEL org.opencontainers.image.title="Redirector"
LABEL org.opencontainers.image.description="A minimal URL redirection service"

EXPOSE 8080

VOLUME ["/data"]

CMD ["uvicorn", "redirector.main:app", "--host", "0.0.0.0", "--port", "8080"]
