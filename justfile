# Gestor Local — tarefas do projeto (backend uv + front pnpm)
set shell := ["bash", "-uc"]

# lista as tarefas disponíveis
default:
    @just --list

# instala/sincroniza dependências (uv sync + pnpm install)
setup:
    cd backend && uv sync
    cd web && pnpm install

# sobe o backend (API + app buildado) em http://127.0.0.1:4747
run:
    uv run --project backend backend/app.py

# sobe o backend sem abrir o navegador
run-nobrowser:
    uv run --project backend backend/app.py --no-open

# frontend em modo dev com hot reload em http://127.0.0.1:5173
dev:
    cd web && pnpm dev

# build do frontend (é o que o backend serve em /)
build:
    cd web && pnpm build

# testes do backend (pytest) e do frontend (vitest)
test: test-backend test-web

test-backend:
    cd backend && uv run pytest

test-web:
    cd web && pnpm test

# lint do backend (ruff + pyright) e do frontend (oxlint)
lint: lint-backend lint-web

lint-backend:
    cd backend && uv run ruff check . && uv run pyright

lint-web:
    cd web && pnpm lint

# formata o frontend (oxfmt) e corrige o que o ruff apontar no backend
format:
    cd web && pnpm format
    cd backend && uv run ruff check --fix .

# lint + testes
check: lint test
