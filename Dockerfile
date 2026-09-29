# syntax=docker/dockerfile:1

FROM python:3.14-slim-trixie AS python-base

# ---------------------------------------------------------------- frontend
FROM node:24-slim AS web

WORKDIR /web
RUN npm install -g pnpm@10
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# ---------------------------------------------------------------- backend
FROM python-base AS backend-build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --project backend

# alvo exclusivo de just docker-test; não faz parte da imagem publicada
FROM backend-build AS tests
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --project backend

# ---------------------------------------------------------------- runtime
FROM python-base AS runtime
ENV PYTHONUNBUFFERED=1 \
    AIM_HOST=0.0.0.0 \
    AIM_PORT=4747

# instaladores e suas cópias vendorizadas ficam fora do runtime
RUN python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip \
    && groupadd --gid 10001 aim \
    && useradd --uid 10001 --gid aim --create-home --shell /usr/sbin/nologin aim

WORKDIR /app
COPY --from=backend-build --chown=10001:10001 /app/backend/.venv backend/.venv
COPY --chown=10001:10001 backend/*.py backend/
COPY --chown=10001:10001 statusline/ statusline/
COPY --from=web --chown=10001:10001 /web/dist web/dist
USER 10001:10001

EXPOSE 4747
CMD ["/app/backend/.venv/bin/python", "/app/backend/app.py", "--no-open"]
