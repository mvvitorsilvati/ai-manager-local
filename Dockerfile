# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- frontend
FROM node:22-slim AS web

WORKDIR /web
RUN npm install -g pnpm@10
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# ---------------------------------------------------------------- runtime
FROM python:3.14-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    AIM_HOST=0.0.0.0 \
    AIM_PORT=4747

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --frozen --project backend
COPY backend/*.py backend/
COPY --from=web /web/dist web/dist

EXPOSE 4747
CMD ["uv", "run", "--project", "backend", "backend/app.py", "--no-open"]
