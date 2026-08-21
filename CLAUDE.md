# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Avie — internal system for Fabiana Montemor's image/style consulting business. Covers the full business cycle: public lead capture via a diagnostic wizard, client CRM (Kanban), consultation scheduling, personalized report generation, and payment tracking. Deliberately minimal stack (no frontend build step, SQLite locally) so it can be maintained by non-developers.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # set a random SECRET_KEY

flask db upgrade                # apply migrations
flask create-admin              # create a staff user; prompts for role: owner | marketing
flask run                       # http://127.0.0.1:5000

pytest                          # run all tests
pytest tests/test_basic.py::test_name   # run a single test
```

After changing `models.py`, always generate a migration instead of hand-editing the DB:
```bash
flask db migrate -m "description"
flask db upgrade
```

There is no `pytest.ini`/`pyproject.toml` — pytest runs with defaults, all tests live in `tests/test_basic.py`.

## Architecture

**App factory** (`app.py`): `create_app(config_class=Config)` builds the Flask app; a module-level `app = create_app()` exists for the gunicorn entrypoint (`app:app`, see `Procfile`). CLI commands (`create-admin`, `backup-db`) are registered via `register_cli(app)` inside the same file. `create-admin` sets `User.role` to `owner` (full access, approves/publishes campaigns) or `marketing` (creates/edits campaigns, cannot approve).

**Extensions** (`extensions.py`): uninitialized instances (`db`, `login_manager`, `migrate`, `limiter`, `mail`) created at import time, bound to the app in `create_app`. `limiter` uses in-memory storage — fine for the current single-process deploy; switch `storage_uri` to Redis if the app ever runs multiple instances.

**Config** (`config.py`): env-driven via `.env` (`python-dotenv`). `AVIE_ENV=production` requires `SECRET_KEY` (raises at import otherwise) and turns on `SESSION_COOKIE_SECURE`. `_normalize_database_url` rewrites `postgres://` → `postgresql://` for SQLAlchemy 2.x compat (Render/Heroku/Railway hand out the old scheme). SQLite is used unless `DATABASE_URL` is set (Postgres in production). `TestConfig` uses in-memory SQLite and disables CSRF/rate limiting.

**Blueprints** (`blueprints/`), all registered in `create_app`:
- `public` — landing (`/`), diagnostic wizard (`/diagnostico`), partial-lead capture (`/diagnostico/lead-parcial`), campaign landing pages (`/lp/<slug>`). Has a `before_request` hook that captures `utm_*`/`gclid`/`fbclid` into the session on first touch, applied to `Client` on any subsequent form submit (`_apply_utm`).
- `auth` — login/logout.
- `dashboard` — `/painel` Kanban overview.
- `clients` — client CRUD, status transitions, consultations, payments, all under `/painel/clientes`.
- `reports` — personalized report drafting/sending.
- `campaigns` — landing page creative management under `/painel/campanhas` (see below).

**Models** (`models.py`): `User` (role: `owner`/`marketing`), `Client` (+ `utm_source/medium/campaign/content/term` attribution fields), `StyleProfile`, `Consultation`, `StyleReport`, `Payment`, `Campaign`. Status/choice constants (`CLIENT_STATUSES`, `CAMPAIGN_STATUSES`, etc.) live here and are injected into every template via the `inject_globals` context processor in `app.py`, along with a `label_for(choices, key)` helper.

**Campaign/creative system**: lets `marketing` test different landing page heroes (title, subtitle, CTA, image URL, accent color) per traffic campaign without touching the main landing page. Flow: `rascunho` (draft, editable) → `em_revisao` (submitted) → `publicado` (live at `/lp/<slug>`) or bounced back to `rascunho` with a `review_note`. Only `owner` can approve/reject/unpublish (`owner_required` decorator in `blueprints/campaigns.py`). `templates/landing.html` takes an optional `campaign` context var — when present, it overrides the hero section only (rest of the page stays brand-consistent); `preview=True` renders it for a logged-in user before publish. Hero images are external URLs, not uploads — Render's filesystem is ephemeral, so anything saved to local disk is wiped on every deploy.

**Reports** (`reports_engine.py`): `generate_report_draft(client, profile)` builds a first-pass report text from the diagnostic answers; the consultant always reviews/edits before sending. No AI/external service involved by design — the roadmap in README.md notes this as a future integration point.

**Email** (`emails.py`): `send_diagnostic_confirmation` no-ops (logs only) when `MAIL_SERVER` isn't configured, so the public form keeps working before an email provider is set up.

**Deployment**: Render.com. The web service (`avie-app`) was created manually, so it does **not** auto-apply `render.yaml` — its settings (build/start command, env vars) must be kept in sync by hand in the Render dashboard. `.python-version` pins `3.11.9` (Render's default can be much newer and has broken `psycopg2-binary` wheels before). Migrations/admin creation are run one-off via the Render Shell tab (`flask db upgrade`, `flask create-admin`).

## Frontend

No build step: Bootstrap, fonts, and the brand mark are vendored under `static/` (no CDN — the app must keep working if a visitor's network blocks Google Fonts/jsDelivr). Brand color tokens are CSS variables in `static/css/style.css`; typography in `static/css/fonts.css`. Templates extend `templates/base.html` (Jinja); form fields render via the `render_field` macro in `templates/_formhelpers.html`.
