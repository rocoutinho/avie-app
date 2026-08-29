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

**App factory** (`app.py`): `create_app(config_class=Config)` builds the Flask app; a module-level `app = create_app()` exists for the gunicorn entrypoint (`app:app`, see `Procfile`). CLI commands (`create-admin`, `seed-admin`, `backup-db`) are registered via `register_cli(app)` inside the same file. `create-admin` (interactive) and `seed-admin` (non-interactive, reads `ADMIN_NAME`/`ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_ROLE` from env, idempotent, no-ops if the env vars are missing or the user already exists — used in production, see Deployment below) both set `User.role` to `owner` (full access, approves/publishes campaigns) or `marketing` (creates/edits campaigns, cannot approve).

**Extensions** (`extensions.py`): uninitialized instances (`db`, `login_manager`, `migrate`, `limiter`, `mail`) created at import time, bound to the app in `create_app`. `limiter` uses in-memory storage — fine for the current single-process deploy; switch `storage_uri` to Redis if the app ever runs multiple instances.

**Config** (`config.py`): env-driven via `.env` (`python-dotenv`). `AVIE_ENV=production` requires `SECRET_KEY` (raises at import otherwise) and turns on `SESSION_COOKIE_SECURE`. `_normalize_database_url` rewrites `postgres://` → `postgresql://` for SQLAlchemy 2.x compat (Render/Heroku/Railway hand out the old scheme) — kept as an opt-in escape hatch even though production currently runs SQLite (see Deployment). SQLite is used unless `DATABASE_URL` is set. `TestConfig` uses in-memory SQLite and disables CSRF/rate limiting.

**Blueprints** (`blueprints/`), all registered in `create_app`:
- `public` — landing (`/`), diagnostic wizard (`/diagnostico`), partial-lead capture (`/diagnostico/lead-parcial`), campaign landing pages (`/lp/<slug>`), public blog (`/blog`, `/blog/<slug>`). Has a `before_request` hook that captures `utm_*`/`gclid`/`fbclid` into the session on first touch, applied to `Client` on any subsequent form submit (`_apply_utm`).
- `auth` — login/logout.
- `dashboard` — `/painel` Kanban overview.
- `clients` — client CRUD, status transitions, consultations, payments, all under `/painel/clientes`.
- `reports` — personalized report drafting/sending.
- `campaigns` — landing page creative management under `/painel/campanhas` (see below).
- `blog` — blog post drafting/review/publish under `/painel/blog` (see below).

**Models** (`models.py`): `User` (role: `owner`/`marketing`), `Client` (+ `utm_source/medium/campaign/content/term` attribution fields), `StyleProfile`, `Consultation`, `StyleReport`, `Payment`, `Campaign`, `BlogPost`. Status/choice constants (`CLIENT_STATUSES`, `CAMPAIGN_STATUSES`, `BLOG_POST_STATUSES`, etc.) live here and are injected into every template via the `inject_globals` context processor in `app.py`, along with a `label_for(choices, key)` helper.

**Campaign/creative system**: lets `marketing` test different landing page heroes (title, subtitle, CTA, image URL, accent color) per traffic campaign without touching the main landing page. Flow: `rascunho` (draft, editable) → `em_revisao` (submitted) → `publicado` (live at `/lp/<slug>`) or bounced back to `rascunho` with a `review_note`. Only `owner` can approve/reject/unpublish (`owner_required` decorator in `blueprints/campaigns.py`). `templates/landing.html` takes an optional `campaign` context var — when present, it overrides the hero section only (rest of the page stays brand-consistent); `preview=True` renders it for a logged-in user before publish. Hero images are external URLs, not uploads — Render's filesystem is ephemeral, so anything saved to local disk is wiped on every deploy.

**Blog system**: content-marketing funnel — articles are drafted/tested on `/blog` before being manually reused on LinkedIn. Same approval flow and `owner_required` pattern as campaigns (`blueprints/blog.py`, mirrors `blueprints/campaigns.py` almost 1:1): `rascunho` → `em_revisao` → `publicado` (live at `/blog/<slug>`, listed at `/blog`) or bounced back to `rascunho` with a `review_note`. `BlogPost.body_markdown` is authored as Markdown and rendered to HTML via the `markdown` Jinja filter (`blog_engine.render_markdown`, registered in `create_app`) — trusted staff-authored content, not sanitized beyond what the `markdown` library does by default (same trust level as `Campaign.hero_image_url`). `blog_engine.format_date_pt` (Jinja filter `pt_date`) formats dates in Portuguese month names, since `strftime('%B')` depends on the server locale (renders in English in production). `templates/blog_post.html` is shared between the public route and the `owner_required`-free `blog.preview` admin route (`preview=True` flag, same pattern as the campaign preview). Cover images are external URLs (same ephemeral-disk reasoning as campaigns) and back `og:image` per post (`base.html`'s `{% block og_image %}`) for LinkedIn share previews. **Blog posts are subject to the same ephemeral-disk data loss as everything else** (see Deployment) — unlike ad-hoc CRM records, published articles are a real content investment, so this is worth reconsidering once the blog has real posts worth keeping.

**Reports** (`reports_engine.py`): `generate_report_draft(client, profile)` builds a first-pass report text from the diagnostic answers; the consultant always reviews/edits before sending. No AI/external service involved by design — the roadmap in README.md notes this as a future integration point.

**Email** (`emails.py`): `send_diagnostic_confirmation` no-ops (logs only) when `MAIL_SERVER` isn't configured, so the public form keeps working before an email provider is set up.

**Deployment**: Render.com, **free plan, zero cost** — deliberate choice while the site is experimental (see `render.yaml`). No Postgres database: production runs on SQLite same as local dev. The free plan's disk is **ephemeral** — `instance/avie.db` is wiped on every deploy and on restarts after idle spin-down, so there is no real data persistence right now; don't add features that assume production data survives across deploys without flagging that limitation. `startCommand` (`flask db upgrade && flask seed-admin && gunicorn app:app --bind 0.0.0.0:$PORT`) re-applies migrations and recreates the admin user from `ADMIN_*` env vars on every boot, so the site is always usable again after a data wipe without a manual step. The web service (`avie-app`) was created manually, so it does **not** auto-apply `render.yaml` — its settings (plan, build/start command, env vars) must be kept in sync by hand in the Render dashboard. `.python-version` pins `3.11.9` (Render's default can be much newer and has broken `psycopg2-binary` wheels before, even though that package is currently unused at runtime). When the business justifies real cost: set `DATABASE_URL` to a Postgres connection string and switch the plan back to `starter` for a persistent disk/database.

## Frontend

No build step: Bootstrap, fonts, and the brand mark are vendored under `static/` (no CDN — the app must keep working if a visitor's network blocks Google Fonts/jsDelivr). Brand color tokens are CSS variables in `static/css/style.css`; typography in `static/css/fonts.css`. Templates extend `templates/base.html` (Jinja); form fields render via the `render_field` macro in `templates/_formhelpers.html`.
