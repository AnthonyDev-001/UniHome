> Product name normalized to UniHome. Original draft retained in the supplied attachment. Phase 0 architecture was approved; unresolved business/legal/provider decisions remain proposals. Baseline observations describe the pre-Phase-1 audit, not the current implementation.

# UniHome — Codex Implementation Roadmap

**Repository to fork:** https://github.com/victor-law-create/learning  
**Companion requirements:** `PRD.md`  
**Principle:** Small auditable pull requests; maintain working existing code; never collect live funds or claim legally binding documents without external approvals.

## Current source baseline (reviewed)

The repository uses Django 5.2.7, Django REST Framework, Simple JWT and SQLite, with `accounts`, `feed`, `marketplace`, `unihome_project`, `manage.py`, and dependency requirements under `backend/`. Existing functionality includes user registration/token login, a social Post API, carts/checkout/orders, models and a few tests. Its README is minimal; no frontend application is present.

Initial code-review risks to verify with tests:
- `feed.views.PostViewSet` uses `IsAuthenticatedOrReadOnly` without post-author object-level write authorization.
- Django settings have unconditional `DEBUG=True` and a fallback SECRET_KEY.
- `marketplace.views.CartViewSet.add_item` casts arbitrary quantity to int without positive-number/error validation.
- `CheckoutView` lacks atomic transaction handling and independently verified payment/escrow support; its 12% fee is hardcoded and unexplained.
- Product orders reference posts with cascading deletion, potentially destroying historical order lines on deletion.
- Media and public API behavior lack full documented controls and tests.

Review each against the latest fork and record confirmed test results; do not mislabel code inspection as successful runtime testing.

## Phase 0 — Fork, audit and design sign-off

**Deliverables:** `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/ROADMAP.md`, endpoint/permission inventory, current test results, issue backlog, open decisions.

**Tasks:** Fork to a repository you control; connect that fork to Codex. Inspect code, configs, migrations, license and requirements. Run environment setup and `python manage.py check`, `python manage.py check --deploy`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test` in isolated development database. Create architecture proposal for property/rental modules and frontend. Do not modify code without approval.

**Exit gate:** Owner approves requirements, scope and architectural decisions.

## Phase 1 — Stabilize and secure original backend

**Deliverables:** Independently reviewable security/quality PR.

**Tasks:** Ownership permissions on `Post` and any affected resources; secure settings from environment; safe Django static/media/security configuration; robust serializer validation; registration/password protections; cart quantity validation; checkout atomicity and order snapshot preservation; remove/harden misleading payment completion semantics; logging, environment template, admin registrations, better README and CI test workflow. Preserve migrations/API compatibility where feasible.

**Tests:** Anonymous and cross-account edits rejected; positive quantity and price validation; duplicate checkout and failures cannot create partial order; stable database migrations; no secrets in code; CI green.

**Exit gate:** Critical/high bugs addressed and baseline regression suite green.

## Phase 2 — Rental data model and agent verification

**Deliverables:** `properties` and `verification` APIs with database migrations, admin screens and tests.

**Tasks:** Separate Property and Unit/Bed/Room entities, media and price breakdown, listing status transitions, availability logic, landlord/agent identity and authorization to list, admin review and suspension, data access controls. Do not reuse social feed Post as property record. Image/video upload validation and secure hosting strategy.

**Tests:** Unverified agent cannot publish; non-owner cannot modify listing; inactive units not bookable; concurrent reservation protections; video constraints; moderation audit events.

**Exit gate:** Admin can approve sample properties; users can retrieve only approved listings.

## Phase 3 — Responsive tenant/agent interface and discovery

**Deliverables:** Mobile-first frontend plus API contracts.

**Tasks:** Decide Next.js/React vs lower-complexity alternative; implement sign-in, search, price/rent-period filters, student/long-term rental tabs, property detail gallery/video, verified marker and full fee disclosure. Build agent property editor and dashboards. Handle slow connections, keyboard accessibility and errors.

**Tests:** Search and filters match seeded data; no hidden fees; invalid listings do not surface; mobile responsive flows pass basic browser tests.

**Exit gate:** Users can discover and inspect a verified property without fake listing or payment claims.

## Phase 4 — Viewings, rental applications and agreement sandbox

**Deliverables:** `viewings`, `rentals`, and `agreements` modules behind feature flags.

**Tasks:** Booking availability, scheduling and notifications; rental offer and fee breakdown; controlled agreement templates; draft/versioned PDFs; authorized signing-provider adapter and mock sandbox; signatory sequence and tamper-evident evidence record; signed-file access. Obtain Nigerian lawyer-approved templates and formalities before any legally binding launch.

**Tests:** Reservation conflict rejected; terms immutable after signing; version change requires re-signing; only authorized signatories can sign/download; all required parties sign before payment eligibility; audit preserved.

**Exit gate:** Sandbox demonstration from property to signed demo agreement works. No false legal guarantees.

## Phase 5 — Protected payment and dispute **sandbox only**

**Deliverables:** `payments`, `disputes`, `audit`, and reconciliation adapters.

**Tasks:** Provider-neutral transaction model and strict state machine; simulated custody/funding/release/refund in isolated environment; signed webhook verification; idempotent event handling and reconciliation; handover evidence, inspection windows, dispute freeze and staff resolution workflow. Document provider contract requirements and edge cases.

**Tests:** Forged webhook rejected; duplicate and out-of-order events safe; double payout impossible; no payment before signed agreement; dispute prevents release under defined policy; admin action audited; refund vs release mutually exclusive.

**Exit gate:** All happy, failure and abuse scenarios pass in sandbox. Do not handle real money yet.

## Phase 6 — Commercial compliance, live-provider integration and deployment

**Prerequisites:** Nigerian lawyer review of tenancy and signing flows, jurisdiction/stamp-duty requirements, approved data protection practices, contract with a suitable authorized holding/release provider, approved operational disputes/reconciliation runbook.

**Tasks:** Sign-provider and payment-provider production integration, security review, load/performance tests, provider webhook and refund certification, deployment pipeline, backup/restore tests, environment controls, error monitoring, incident response, privacy pages, support playbooks and limited controlled launch. Require explicit human approval before any real payment or deployment.

**Exit gate:** Proven and reviewed commercial readiness, not just functioning tests.

## Phase 7 — Marketplace reuse and measured expansion

Preserve existing `marketplace` domain. Later complete seller verification, product delivery tracking, customer protection, payment/refunds via an approved separate policy, and shopping frontend. Share identity, media, trust, audit and provider infrastructure where appropriate; **do not share rental agreement or rental checkout states blindly with ecommerce orders**. Only add after rentals are stable.

## Codex operating rules

- Work only in a controlled fork or development branch, never write to the upstream original unless explicitly authorized by its owner.
- Read the PRD first; make assumptions explicit; ask for approval on policy decisions.
- One pull request per coherent phase or smaller functional vertical slice.
- Use existing code and migration history; avoid destructive migrations or global rewrites.
- No production secrets, KYC credentials, card data, funds or real tenancy agreement materials in test data.
- No live payments, payouts, e-signature invitations or production deployment without user and relevant external approvals.
- Implement role-based access and threat-model tests before expanding functionality.
- For each PR provide summary, file list, tests run and actual results, screenshots of frontend where applicable, risks, rollback and manual test checklist.
- Block merging on failing CI, regression or unresolved critical security issues.

## Copy-paste first Codex task

You are the lead engineer reviewing my fork of https://github.com/victor-law-create/learning. I am building UniHome: a Nigerian student-lodge and long-term rental platform with verified property agents/landlords, property photos and videos, bookings for inspections, fully disclosed rental costs, legally reviewed electronic agreements, and partner-operated protected payments with handover and disputes. General Marketplace will be a separate later expansion, not a rental data model.

Read `PRD.md` and `ROADMAP.md` if present, or ask me to attach their contents. Audit the existing Django apps, API, database and tests. Confirm issues by inspection and running commands in an isolated environment. Deliver the endpoint/permission inventory, prioritized bugs, proposed new Django models/apps, deployment and security risks, and PR-by-PR implementation plan. Specifically investigate ownership authorization for posts, unsafe Django production defaults, cart quantity handling, unatomic checkout, hardcoded fee, and order-item cascade on product deletion.

Do not make code changes, commit, push, open PRs, deploy, sign agreements or touch live money in this first task. Present an actionable review and wait for my approval for Phase 1. Use a separate branch for subsequent implementation and include tests for each change.
