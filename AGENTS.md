# Repository Guidelines

## Project Structure & Module Organization

`backend/` contains the Python 3.14 HTTP API and local file operations; `backend/tests/{unit,integration,e2e}/` separates pure logic, filesystem workflows, and live HTTP routes. `web/src/` contains the React/TypeScript app: put screens in `views/`, reusable UI in `components/`, hooks in `hooks/`, and API and formatting helpers in `lib/`. Frontend unit tests live beside their modules as `*.test.ts(x)`; browser tests and fixtures live in `web/e2e/`. `site/` holds the public landing page and assets, while `statusline/` contains installer scripts and templates. The backend serves the built `web/dist/` app.

## Build, Test, and Development Commands

- `just setup`: sync backend dependencies with uv, install frontend packages with pnpm, and enable Git hooks.
- `just build`: type-check and build the frontend for the backend to serve.
- `just run-nobrowser` and `just dev`: run the API on port 4747 and the Vite frontend on port 5173 in separate terminals.
- `just check`: run backend Ruff/Pyright and pytest, plus frontend oxlint and Vitest.
- `just e2e`: build the frontend and run Playwright against a fixture-backed server. Run `just coverage` for the backend HTML coverage report.

## Coding Style & Naming Conventions

Keep Python code within Ruff's 120-character limit and follow its import rules; Pyright runs in basic mode. TypeScript uses two-space indentation, double quotes, and no semicolons; run `just format` for oxfmt and Ruff fixes. Name React components in PascalCase, hooks with `use` prefixes, and Python tests `test_*.py`. Route frontend HTTP calls through `web/src/lib/api.ts`. Treat `web/src/components/ui/` as generated shadcn code.

## Testing Guidelines

Add pytest tests at the matching backend level and colocate Vitest tests with frontend code. Use Playwright for browser flows; `just test` runs pytest and Vitest, while `just e2e` runs browser tests separately. The backend reports branch coverage, but no minimum percentage is configured. Validate affected behavior and run `just check` before opening a PR.

## Commits, Pull Requests & Security

Use short topic branches such as `feat/...` or `fix/...` and Portuguese imperative Conventional Commits, for example `fix(backend): corrige conflito no save`. Keep each commit focused. Open a PR against `main` using the template: describe the change, link an issue when applicable, list validation commands and expected results, and attach before/after screenshots for visual changes. Keep credentials, `.env`, backups, and audit logs out of diffs. Preserve the backend's `X-AIM` and path checks on write routes; see `CONTRIBUTING.md` and `.github/SECURITY.md` for details.
