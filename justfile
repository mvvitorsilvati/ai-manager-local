# Gestor Local — tarefas do projeto (backend uv + front pnpm)
set shell := ["bash", "-uc"]

# lista as tarefas disponíveis
default:
    @just --list

# instala/sincroniza dependências (uv sync + pnpm install) e liga os git hooks
setup:
    cd backend && uv sync
    cd web && pnpm install
    just hooks

# aponta o Git para os hooks versionados em .githooks (pre-commit roda `just check`)
hooks:
    chmod +x .githooks/pre-commit
    git config core.hooksPath .githooks
    @echo "hooks ativados (pule com: git commit --no-verify)"

# para a instância que estiver rodando na porta 4747
stop:
    @pid=$(lsof -nP -i :4747 -t 2>/dev/null | head -1); \
    if [ -n "$pid" ]; then kill "$pid" && echo "instância na 4747 encerrada (pid $pid)"; else echo "nenhuma instância rodando na 4747"; fi

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

# coverage do backend com relatório HTML em backend/htmlcov
coverage:
    cd backend && uv run pytest --cov-report=html

# testes E2E (Playwright) — builda o front e sobe o backend com a fixture
e2e:
    cd web && pnpm build && pnpm test:e2e

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

# ------------------------------------------------------------------ container
# build da imagem (tag padrão do time: localhost/<repo>-py-<versão>:<versão do pyproject>)
docker-build:
    podman build -t localhost/gestor-local-py-3.14:0.1.0 .

# sobe o painel em http://127.0.0.1:4747 montando o seu HOME (fontes, backups e audit)
docker-run:
    podman run --rm --name gestor-local \
      -p 127.0.0.1:4747:4747 \
      -e HOME=/host-home -e GESTOR_HOST=0.0.0.0 \
      -v "$HOME":/host-home \
      localhost/gestor-local-py-3.14:0.1.0

# roda a suíte de testes dentro da imagem (usa a venv embutida, sem rede)
docker-test:
    podman run --rm --name gestor-local-test \
      -v "$PWD":/workspace -w /workspace/backend \
      localhost/gestor-local-py-3.14:0.1.0 \
      /app/backend/.venv/bin/python -m pytest
