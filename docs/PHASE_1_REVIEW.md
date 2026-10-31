# Phase 1 — foundation review

Review branch: `phase-1-foundation`. Base: audited commit `b2bd9531448104d2199cfb73631fb1e2dd06e77f`. Ready for owner review; no rental, live-payment or deployment work included.

## Changes and purpose

- Renamed Python project package and management/ASGI/WSGI references to `unihome_project`; retained Django app labels and original migrations.
- Removed public fallback secret, made development opt-in, required explicit production hosts/strong secret, added transport/cookie/static/media/environment configuration and basic console logging.
- Enforced author/staff write permissions; validated product pricing at API and database levels; constrained image formats/sizes and made posting timestamps read-only.
- Applied password validators and atomic account provisioning; added throttled account recovery, JWT refresh rotation/blacklist and password-change revocation, including explicit refresh password-state validation.
- Validated cart inputs before writes; bounded quantities; unique cart/product constraint; row-locked mutations and atomic checkout, optional idempotency key, explicit unpaid response and stored fee breakdown.
- Preserved new order descriptions/prices independently of mutable/deleted source products; protected order users; read-only order admin. Legacy descriptions are best-effort current copies, not reconstructed originals. Unknown old currency/breakdowns remain unknown.
- Added preflight guards for invalid legacy records, migration upgrade tests, PostgreSQL concurrency tests, production configuration tests and PostgreSQL-backed GitHub Actions.
- Updated vulnerable baseline pins to Django 5.2.18 (same LTS series), DRF 3.18.2, Pillow 13.0.0, PyJWT 2.15.1 and sqlparse 0.6.0. PostgreSQL driver is in requirements-dev.txt, also required by PostgreSQL deployments.
- Saved the supplied requirements/roadmap with UniHome naming and draft-policy caveats, Phase 0 evidence, architecture, threat model and developer README. License/history retained.

## Verification performed

Python 3.12 in an isolated virtualenv, PostgreSQL 16 in a disposable local container, no production data or real external signing/payment services.

- PostgreSQL suite: **25 tests, 25 passed**, including duplicate simultaneous checkout with/without keys and simultaneous cart additions.
- SQLite suite: **25 discovered, 22 passed, 3 explicitly skipped** (PostgreSQL row-locking tests).
- `manage.py check`: passed.
- `makemigrations --check --dry-run`: passed, no changes detected.
- Fresh migrations and legacy upgrade/preflight scenarios exercised by test suites.
- Deployment configuration subprocess checks pass with private-secret-shaped test input, explicit fictional host and opt-in HSTS subdomains/preload. Missing secrets/hosts fail startup. These test values are not deployment credentials or a decision about real domain policy.
- `pip check`: passed. `pip-audit` against all pinned production requirement entries: no known vulnerabilities reported after upgrades; advisory availability is time-dependent and this is not a penetration test or proof against unknown vulnerabilities.
- `git diff --check`: passed.
- Renamed application started through `manage.py runserver` against a temporary migrated SQLite database; real loopback HTTP requests verified public post reads (200), registration (201) and JWT login (200). Credential values were withheld. The temporary server was stopped after validation.

GitHub-hosted CI is configured but must be observed on the pushed branch; local results do not prove hosted CI ran. Tests deliberately inject a checkout exception and assert rollback; its logged 500 is expected within that passing test.

## Compatibility and remaining limitations

Existing endpoint paths and public post-list response shape retained. Non-author writes and invalid values now fail. Existing JWTs require fresh sign-in. Checkout preserves the inherited 12% Marketplace uplift, now disclosed/rounded/snapshotted; this is not a new rental pricing policy. New orders explicitly use NGN. Idempotency keys are optional for legacy clients, but clients should use them for reliable retry responses.

Production-mode HSTS include-subdomains/preload intentionally remain explicit operator choices. Django deploy checks warn until those choices are configured. CI tests opt-in against a fictional hostname only. No real domain was configured.

Recovery backend is tested with in-memory email. Real SMTP, trusted frontend reset page and support handling of duplicate legacy email addresses remain unconfigured. Synchronous email timing may reveal eligibility; queue email before public launch. Default process-local throttles need shared-cache/edge controls for distributed operation. Contact/email verification is not implemented yet.

No production upload service, media malware/metadata pipeline, private identity storage, rental permissions/audit system, frontend, provider integration, real documents/funds, deployment, backup recovery exercise or load test exists. Global product and financial legal gates from the PRD still apply. Keep legacy Marketplace out of a commercial launch until its separate commercial policy is approved.

The changes stop short of converting the User model or decoupling the Profile/Cart creation signal; atomic API provisioning fixes partial registration, while identity/role restructuring belongs to the next domain phase. No current user data was migrated outside isolated databases.

## Review checklist

1. Use README setup steps with a disposable database; check startup requires secrets and production hosts.
2. Register/login two accounts. Verify public reads, author edits and denied cross-account writes.
3. Submit invalid prices/quantities; verify 400 and no cart writes. Exercise a valid cart checkout and retry with the same Idempotency-Key.
4. Confirm response says unpaid and discloses NGN subtotal, legacy fee and total. Delete a source product and verify the order snapshot survives.
5. Test recovery through a local email backend or approved development SMTP; verify single-use reset and revoked old JWTs. Do not send real signing invitations or collect identity documents.
6. Review migrations against a backup copy of any existing database before rollout; invalid legacy records require deliberate repair.
7. Review hosted PostgreSQL CI before merging. Confirm the rename does not affect external startup configuration.

Rollback: see README. Prefer forward correction. Reversing schema after new snapshots or deleted source products can be unsafe; do not restore old non-null/CASCADE semantics blindly. No merge or deployment is part of this change.

Next phase, after review: property/rentable inventory schema, authority verification, moderation, private evidence and permission tests. Financial/legal policy choices remain separate approval gates.
