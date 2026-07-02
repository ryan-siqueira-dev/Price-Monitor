# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `price_monitor/`. FastAPI routes are in `api.py`, CLI commands in `cli.py`, SQLAlchemy models in `models.py`, and orchestration in `services/`. Store search integrations and matching rules belong in `search/`; direct-URL extraction belongs in `scrapers/`; Telegram delivery belongs in `notifications/`.

Database migrations are under `alembic/versions/`. Tests live in `tests/` and mirror behavior rather than package layout, for example `test_search.py` and `test_monitor.py`. `data/` contains the runtime SQLite database and browser sessions; treat it as local state, not source code.

## Build, Test, and Development Commands

Use Python 3.11 or newer and install the development extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
alembic upgrade head
```

Run `uvicorn price_monitor.api:app --reload` for the local API or `price-monitor --help` for CLI usage. `docker compose up --build -d` starts the API and 24-hour scheduler.

Before submitting changes, run:

```bash
pytest
ruff check .
ruff format --check .
python -m compileall price_monitor tests alembic
alembic check
```

## Coding Style & Naming Conventions

Follow Python 3.11 syntax, four-space indentation, type hints, and Ruff's 100-character line limit. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and descriptive provider names such as `BrowserSearchProvider`. Keep network failures isolated by provider and expose actionable error messages.

## Testing Guidelines

Pytest is configured through `pyproject.toml`. Name files `test_*.py` and tests `test_<behavior>`. Add regression coverage for parser changes, matching rules, provider configuration, API behavior, and migrations. Use mocked transports or fixtures for deterministic tests; do not depend on live store pages or Telegram.

## Commit & Pull Request Guidelines

The current history is small and uses brief Portuguese summaries, so no strict convention is established. Prefer concise imperative messages such as `corrige filtro de acessórios` or `add Carrefour provider tests`. Keep commits focused.

Pull requests should explain the behavior changed, risks to scraping or persisted data, and commands run. Link related issues. Include API examples when contracts change and migration notes when the schema changes; screenshots are only needed for future UI work.

## Security & Configuration

Copy `.env.example` to `.env`, but never commit `.env`, Telegram credentials, `data/`, or `data/auth/`. The API has no authentication; keep it bound to localhost or behind Tailscale. Do not implement CAPTCHA bypasses or expose browser session data.
