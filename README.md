# UniHome

UniHome is a Nigerian student accommodation and long-term rental platform under development. This repository currently contains the secured Django foundation, account and social Post APIs, and a separate legacy Marketplace. **Rental listings, signing, protected payments and a frontend are not implemented.** Marketplace checkout creates an **unpaid order**, never a payment confirmation.

Based on `victor-law-create/learning`, with original history and MPL-2.0 license preserved. See [product requirements](docs/PRD.md), [architecture](docs/ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md), [roadmap](docs/ROADMAP.md) and [Phase 1 review](docs/PHASE_1_REVIEW.md).

## Development

Use Python 3.12. Each cloud task already has an isolated workspace; use the existing checkout without creating a worktree unless requested.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
export DJANGO_DEBUG=true
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
cd backend
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

`backend/.env.example` documents variables; Django does not auto-load .env files. Keep secrets out of Git. SQLite is the default for single-user development. Production settings default to DEBUG off and require a private strong secret and explicit hosts. Run `python manage.py check --deploy --fail-level WARNING` under production-shaped settings before considering deployment; passing it alone is insufficient for launch. Django 5.2.18 warns unless HSTS subdomains/preload are enabled: these remain opt-in through `DJANGO_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_HSTS_PRELOAD`. Evaluate domain-wide HTTPS and the persistence of browser preload before enabling them. CI opts in only for its fictional test domain; no real domain policy was changed.

For PostgreSQL integration and concurrency tests, set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` and optionally `POSTGRES_PORT`. Use a disposable development database and a role allowed to create Django's `test_` database. Install `requirements-dev.txt` (includes the PostgreSQL driver). `python manage.py test` runs row-locking tests on PostgreSQL and explicitly skips them on SQLite. Do not rely on SQLite for concurrent checkout. GitHub Actions uses PostgreSQL 16, migration checks and the complete test suite.

## API and compatibility

Existing routes are preserved:

- `POST /api/accounts/register/`, `/api/accounts/token/`, `/api/accounts/token/refresh/`.
- `GET/POST /api/posts/` and `GET/PUT/PATCH/DELETE /api/posts/{id}/`. Reads are public; writes require author or staff authority. Authors are assigned server-side; timestamps are read-only. Product prices must be strictly positive and non-null.
- `GET /api/marketplace/cart/{id}/`; `POST .../add_item/` with product_id/quantity (1–999); `POST .../remove_item/` with item_id. Own carts only.
- `POST /api/marketplace/checkout/`: atomic unpaid order creation, cart clearing only on success. Optional `Idempotency-Key` (1–128 characters) returns the same user's previously created order on retry with HTTP 200; first creation returns 201. Reuse a key only for the same checkout. Without a key, duplicate simultaneous requests yield one order and an empty-cart error. New cart contents are not consumed by a replayed key.

The legacy 12% Marketplace uplift is preserved, explicitly snapshotted and disclosed in the response as subtotal, fee_rate, fee_amount, currency and total_price; rounding uses decimal half-up to two places. This is compatibility behavior, **not approval of that fee or a rental fee policy**. New Marketplace orders use NGN. Invalid input that previously returned 500 now returns 400; non-author writes return 403. Public post-list response shape remains unchanged (pagination reserved for versioned rental APIs).

JWT access tokens last 5 minutes; refresh tokens last one day, rotate and are blacklisted after rotation. Password changes invalidate access tokens and refresh tokens. Existing pre-change tokens require users to sign in again. Run `python manage.py flushexpiredtokens` daily to prune expired blacklist records. Browser token storage strategy remains a frontend architecture decision; avoid localStorage for long-lived credentials.

Account recovery: `POST /api/accounts/password-reset/` with email; `POST /api/accounts/password-reset/confirm/` with uid, token and password. The request endpoint remains disabled (503) until `ACCOUNT_RESET_URL` is a trusted frontend reset page. Configure SMTP with the EMAIL_* variables and DEFAULT_FROM_EMAIL; production reset URLs require HTTPS. Links expire after one hour and are single use. Matching and unknown addresses receive the same success response; duplicate legacy email addresses require support intervention rather than guessing a user. SMTP delivery and a frontend reset page are not configured by this change. Synchronous email timing remains an enumeration consideration; use queued delivery before public launch. Auth endpoints have a shared 20/hour/IP scope; general API defaults are 60/hour anonymous and 1000/hour authenticated. These cache-based limits are a baseline, not a distributed abuse defense: configure a shared cache/edge limits before scale and trust forwarding headers only behind a configured ingress.

## Data migration and rollback

Back up any existing database and test migration against a copy first. Original 0001 migrations remain intact. New migrations reject nonpositive/null product prices, duplicate cart/product lines and quantities outside 1–999. A rejection requires a deliberate data repair decision before retry; migrations do not silently invent prices or discard cart contents.

Existing order totals and line prices are retained. Available legacy product descriptions are copied into new snapshots; this cannot reconstruct original descriptions if products were previously changed. Historical currency and fee breakdown stay unknown (empty currency/null breakdown). New order lines survive product deletion; users referenced by orders cannot be deleted. Use a separately reviewed anonymization/retention policy instead. Orders and order lines are read-only in Django admin; no financial status switch is exposed.

Rollback new code only with the matching project entry points and schema plan. Do not reverse schema migrations after new orders or deleted source products without checking null product references and preserving snapshots: old CASCADE/non-null semantics cannot safely restore lost source records. Prefer a forward fix; restore a tested backup only with explicit authorization and a data reconciliation plan. No backup or production database was modified here.

## Security and release boundaries

Images are limited to 5 MiB and JPEG/PNG/WebP. No production upload serving, malware pipeline, private verification storage or real identity-document collection is configured. Enforce request-body limits at the ingress as well as application validation. No provider keys, card data, customer funds or real agreements belong in development.

The platform still requires rental domains, property authority verification, private media controls, staff audit trails, privacy/retention policy, legal templates, a suitable contracted funds-holding provider, reconciliation/dispute operations and deployment/backup recovery review. No live funds, e-signature invitations or deployment are authorized or enabled by this phase.
