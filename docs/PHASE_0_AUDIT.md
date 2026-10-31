# UniHome — Phase 0 audit and architecture proposal

Status: proposed; awaiting owner approval. No implementation authorized.

## Scope and evidence

Both supplied PRD and roadmap were read in full. They are proposals, not approved business policies. UniHome replaces Vicodom/Vicdom in this proposal. Original attachments and source files remain unchanged. A future branding PR should rename `vicodom_project` to `unihome_project`, update settings/import/ASGI/WSGI/manage references and documentation, and test entry points; do not rename Django app labels or rewrite migrations merely for branding.

Audited repository: https://github.com/victor-law-create/learning at `b2bd9531448104d2199cfb73631fb1e2dd06e77f`, cloned to `/workspace/learning-audit`. This is separate from the existing empty `/workspace/UniHome` checkout. No fork, push, PR, commit, deployment, provider operation or source change was made. Git status was clean after validation.

The code is Django 5.2.7, DRF 3.16.1, SimpleJWT 5.5.1, Pillow and SQLite. Requirements also include Playwright, but there is no frontend or browser suite. README contains no useful setup instructions; no CI, environment example or deployment configuration is present. License is MPL-2.0: preserve notices and obtain advice on applicable source-distribution obligations before distribution; this is not a license clearance.

## Validation

Python 3.12 virtualenv `/tmp/unihome-audit-venv`, exact requirements installed with TLS verification, no dependency declarations changed. Harnesses live outside the repository in `/tmp/unihome-audit`. Django command harness uses the repository settings with only the SQLite path redirected outside the checkout. Probes use an in-memory migrated database, `testserver` allowed host and DEBUG disabled to suppress error-page detail. No production data or real providers used.

| Check | Actual result |
|---|---|
| Dependency installation / pip check | Passed; no broken requirements |
| Django check | Passed, no issues |
| Django check --deploy | Exit 0, **seven security warnings**; not production readiness |
| makemigrations --check --dry-run | Passed, no changes detected |
| Django test | 3 discovered, 3 passed; fresh test database migrations succeeded |
| Anonymous public post GET / JWT password login | 200 / 200 |
| Cross-user cart retrieval | 404, correct owner scoping |
| Cross-user post PATCH / DELETE | 200 / 204, authorization failures |
| Registration with password `1` | 201, configured password validators bypassed |
| Cart quantity zero | 200, persisted zero |
| Cart quantity `abc` / -1 on fresh cart item | 500 / 500; default quantity 1 item remains after error |
| Checkout with injected OrderItem creation failure | 500; order remains with zero lines |
| Normal checkout, rent-unrelated product price 10 | 201; total 11.20, paid=False |
| Delete purchased post | Historical order line count changes 1 to 0 |
| Product with negative / omitted price | Both accepted with 201 |

Deployment warnings: missing HSTS, HTTPS redirect, secure session cookie, secure CSRF cookie, unsafe fallback secret, DEBUG enabled and empty ALLOWED_HOSTS. No dependency advisory scan, browser E2E, PostgreSQL concurrency test, load test, live signing/payment test or production deployment was performed. Probe results demonstrate defects; they are not a passing security regression suite. Sequential checks do not prove concurrency safety.

## Endpoint and permission inventory

Router paths accept their normal trailing slash and format variants. OPTIONS/HEAD follow DRF behavior.

| Endpoint | Methods | Current access / observation |
|---|---|---|
| /api/accounts/register/ | POST | Public; username/email/password, hashes password; no password-strength call, email verification or recovery |
| /api/accounts/token/ | POST | Public credentials exchange for JWT pair |
| /api/accounts/token/refresh/ | POST | Valid refresh token; no application revocation/rotation/blacklist configuration |
| /api/posts/ | GET, POST | Public reads; authenticated creates, author assigned server-side |
| /api/posts/{id}/ | GET, PUT, PATCH, DELETE | Public reads; any authenticated user can modify/delete any post |
| /api/marketplace/cart/{id}/ | GET | JWT required, queryset restricted to caller |
| /api/marketplace/cart/{id}/add_item/ | POST | Own cart only; product must be marked is_product; quantity conversion unsafe |
| /api/marketplace/cart/{id}/remove_item/ | POST | Own cart and item scoped; malformed identifiers not comprehensively validated |
| /api/marketplace/checkout/ | POST | Authenticated; own cart; creates unpaid order and deletes items; no payment processing |
| /admin/ | Django admin routes | Django staff/session controls; domain models are not registered |
| /api/, /api/marketplace/ | Router GET roots | Discovery only; not rental resources |

No profile editing endpoint, roles/verification APIs, rental search, order retrieval API, signing endpoint, provider webhook or payment adapter exists. JWT is the configured DRF authentication; Django session auth is used for admin. No explicit default permission class is configured, so unspecified DRF endpoints inherit AllowAny. No application throttles, pagination, verification, audit trail or role-request flow is present.

## Existing models and migrations

- accounts.Profile: one-to-one built-in User, bio, image and social followers.
- feed.Post: author, content, optional image, product flag, nullable price, category, client-writable date_posted.
- marketplace.Cart / CartItem: one cart per user, post-backed item, quantity. No unique cart/product constraint or strictly-positive business constraint.
- marketplace.Order / OrderItem: user, total, paid flag; line quantity and price. Product and user cascades can erase transaction evidence; product description/currency/fee policy not snapshotted.
- One initial migration in each app; dependency order is consistent and fresh migrations run. No deployed database or existing production data was available to assess upgrade risk.
- User creation signal creates both Profile and Cart; identity is unnecessarily coupled to Marketplace. Failed provisioning can leave partial state outside an encompassing transaction; legacy users without carts are not handled by checkout.

## Prioritized findings

**High — fix before exposing this backend to users:**

1. Broken object authorization on posts (`backend/feed/views.py:5`). This also enables deletion of another seller's product and dependent purchase history.
2. Unsafe production configuration (`backend/vicodom_project/settings.py:24`). Published fallback secret plus JWT signing defaults is dangerous if deployed without a private key. Generate/rotate independent deployment secrets and invalidate affected tokens where applicable. There is no evidence that this repository is currently deployed.
3. Checkout lacks atomicity, locking, idempotency and stable snapshots (`backend/marketplace/views.py:58`). Failure injection confirms partial orders. Concurrent duplication remains an inspection-based risk, not a reproduced concurrency result.
4. Order history cascades (`backend/marketplace/models.py:29`), reproduced on deletion. Use protected/nullable source references and immutable line snapshots, with an explicit retention policy.
5. Cart validation can return 500 after writing state (`backend/marketplace/views.py:18`). Validate before writes; enforce integer bounds, quantity > 0, unique lines and atomic quantity updates.
6. Product price accepts negative/null values (`backend/feed/serializers.py:4`); null product prices can break totals and negative prices permit invalid totals. Add API and database invariants with data cleanup planning.

**Medium — foundational gaps:** registration bypasses password validators; no recovery/email verification, abuse throttling or explicit email identity policy; refresh token lifecycle undefined; no upload size/type/content pipeline or private download access; no pagination/filtering; no operational logging, backup/restore or CI. A hardcoded 12% checkout uplift has no policy/currency/rounding breakdown. Normal checkout leaves paid=False: it must not be described as payment confirmation or escrow. Domain admin files contain no registrations.

## Recommended backend architecture

Use a **modular Django monolith**, DRF `/api/v1/` for new rental APIs and PostgreSQL for integration/production. Preserve existing routes until an explicit deprecation decision. Avoid microservices at this scale. Keep existing migration history; additive schema/data migrations, staged backfills and reversible rollout wherever feasible.

Retain built-in User initially to avoid a disruptive mid-project user-model swap. Use `settings.AUTH_USER_MODEL` for new relations; roles are capabilities through Groups/permissions plus explicit memberships, not one mutually exclusive role string. A tenant may also be a landlord. Preserve Profile but separate identity provisioning from automatic cart creation. Retain JWT compatibility for existing API clients; decide browser authentication explicitly before frontend implementation.

Write domain transitions in service functions under transaction.atomic; serializers validate input, permissions and querysets scope reads/writes, database constraints protect invariants. Record actor, previous/next state, reason, request identifier and timestamp for privileged transitions. State changes require explicit actions; clients cannot directly PATCH approval, funded or signed status.

Add Redis/task worker only when asynchronous media, notifications or provider work begins; use an outbox persisted with domain changes so delivery failures cannot silently lose events. The database remains authoritative. Separate adapters for storage, notifications, signing and payments; feature flags default financial and binding-signature flows off. Preserve Marketplace as a separate bounded domain, never map a rental to a Post/cart/order.

## Proposed relational model

| Domain | Core records and relationships / constraints |
|---|---|
| Identity | Existing User/Profile; role requests and scoped staff capabilities; verified contact methods and recovery records |
| Verification | VerificationCase -> applicant; private DocumentReference; immutable ReviewDecision; PropertyAuthority links a representative to a property, permitted actions, evidence, expiry/revocation. Identity approval alone is not listing authority |
| Properties | Property -> owner/authorized parties, private exact address and public approximate location; Campus/Area; Unit parent hierarchy for building/unit/room/bed with explicit rentable inventory; Amenity; ListingRevision and moderation decision; SavedListing unique(user, listing) |
| Pricing/media | Versioned PriceSchedule with NGN amount and billing period; ChargeLine for deposit/agent/service/utilities/refundability; MediaAsset with object key, checksum, MIME/size, scan/transcode/moderation states, ordering and captions |
| Viewings | AvailabilitySlot, ViewingRequest/Appointment, participants, capacity, confirmation/cancellation and attendance events; separate viewing capacity from accommodation reservation |
| Rentals | Application -> tenant + unit; OfferVersion with immutable cost/terms snapshot; BookingHold expiry; Occupancy/Reservation with date range; HandoverCase, ChecklistItem, Evidence and party acknowledgements |
| Agreements | Approved TemplateVersion by jurisdiction; AgreementVersion -> offer snapshot/hash; required Signatories/authority; SigningSession; immutable SignedArtifact and provider evidence. Revisions require new signatures |
| Payments, later | PaymentIntent -> agreement/offer; ProviderTransaction; unique ProviderEvent(provider,event_id); ProtectedFundsCase; mutually controlled Release/RefundInstruction, ReconciliationRecord and discrepancy queue. Store provider references/status, never pretend this is a custodial wallet |
| Disputes | Case -> rental/funds case, private Evidence, immutable case events, assigned reviewer, Decision and Appeal; actor and deadline policy version retained |
| Operations | AuditEvent, NotificationPreference, OutboxMessage/DeliveryAttempt; restricted sensitive payloads, retention and redaction controls |

Use Decimal amounts and explicit currency, never floats. Store UTC and display Africa/Lagos. Snapshot offers, fees, signatories and policy versions; avoid deriving historical commitments from mutable listing data. Public IDs may be UUIDs but do not replace authorization.

Availability must prevent overlapping occupancy at the actual rentable inventory level. PostgreSQL exclusion constraints suit exclusive inventory/date ranges; shared-bed inventory should have explicit bed records or properly locked capacity accounting. Hierarchical unit/room/bed bookings must conflict with their descendants/ancestors. Define this model before implementing reservations. Use transaction locks and unique keys for acceptance/idempotency; test races on PostgreSQL rather than relying on SQLite behavior.

## Frontend proposal

Responsive Next.js/React + TypeScript web frontend, subject to approval; no native app in the first phase. Suggested areas: public search/results and property detail; account/recovery; tenant saved homes/viewings/applications; representative verification/listing editor/viewings; staff moderation through Django admin first. Add agreement, handover and dispute pages when those workflows exist.

Use generated types from a versioned OpenAPI schema, shared form validation/error conventions and accessible UI components. Separate student lodges from long-term rentals while sharing discovery. Price filters must include billing period and full fee disclosure; do not compare annual and monthly amounts as equivalent without clear normalization. Show which checks a verification badge actually represents.

Use list-first search, compressed responsive images, user-initiated/lazy video, captions and low-bandwidth fallbacks. Keep private evidence outside public media delivery. Prefer same-origin browser access with server-managed secure HttpOnly cookies/BFF and explicit CSRF handling; do not put long-lived refresh tokens in localStorage. Preserve JWT API behavior for supported clients; the exact browser session approach needs a recorded architecture decision and auth tests. Django templates/HTMX remain a lower-complexity alternative if maintaining two runtimes exceeds team capacity.

## Threat model and operational risks

Primary threats: cross-account record access, fraudulent listing authority, approval bypass, malicious uploads, private-ID/address leakage, account takeover, reservation races, signed-term tampering, forged/replayed provider events, duplicate release/refund and staff abuse.

Controls: endpoint permission matrix and denial tests; tiered identity/property approvals; private signed object URLs after authorization; upload quarantine/content scanning and EXIF handling; strict transitions and DB constraints; immutable document evidence; verified callbacks plus independent reconciliation; separation of support/reviewer/financial permissions; dual control for exceptional financial actions; append-only business audit backed by protected storage/export. A database table alone is not tamper-proof against privileged operators.

Production infrastructure is a future design: HTTPS ingress, private PostgreSQL, private object storage for identity/contracts, public derivatives/CDN for approved media, worker queue, secrets manager, monitoring, tested encrypted backups and incident response. No deployment target has been selected. Dependency patch/advisory review is required before release; installed historical pins are a reproducibility baseline, not a security endorsement.

## External and founder decision gates

| Decision | Dependency and safe interim behavior |
|---|---|
| Launch geography | Choose city/campuses/state before jurisdiction rules; no nationwide assumption |
| Listing authority | Decide landlord self-publishing, agent qualifications, documentary review, renewal and revocation; manual approval first |
| Financial partner | Authorized provider must contractually support actual holding, conditional release, refunds, dispute freeze, reconciliation and failure handling; ordinary card collection/splits are insufficient. No provider selected or live funds authorized |
| Fees and commercial model | Approve rent periods, deposits, refundable charges, tax/accounting and revenue; no inherited 12% fee for rentals |
| Agreements/signing | Nigerian counsel approves state-specific templates, witnessing, stamping, authority, consent, evidence and retention; signing vendor must meet those requirements. Demo PDFs remain explicitly nonbinding |
| Student capacity | Counsel determines age/guardian eligibility and signing authority; no invented legal-age workflow |
| Handover/disputes | Approve inspection requirement, evidence, deadlines, nonresponse, decision-maker, appeal and provider freeze semantics; do not hardcode arbitrary windows |
| Privacy/KYC | NDPA-related lawful basis, minimization, retention/deletion exceptions, processor/cross-border arrangements and incident duties require expert review; avoid collecting real IDs in development |
| Operations | Support staffing, moderation/dispute SLA, dual-control responsibilities and recovery runbooks must be staffed before commercial launch |
| Ownership/license | Confirm destination repository and upstream reuse/license obligations before implementation distribution; do not push to upstream |

No legal reference or vendor authorization was independently verified in this audit. The supplied documents identify questions, not evidence of regulatory approval. Protected funds, enforceable signatures, automatic release/refunds and commercial launch remain externally gated. A closed mock pilot is distinct from a commercial MVP; mocks do not satisfy commercial release blockers.

## Prioritized PR plan and approval gates

PRs are proposed only; none opened. Use an owner-approved repository/branch after Phase 0 approval.

1. **P1a: baseline and branding** — record approved PRD/architecture/threat model/roadmap, rename product and Python project entry points safely, reproducible developer setup, pinned supported runtime, CI with check/migration/test gates. Review dependencies/advisories before selecting upgrades. No app-label or migration-history rewrites.
2. **P1b: identity/settings/authorization** — fail-closed production configuration, post owner/staff policy, explicit defaults, password validation, auth abuse controls, recovery/token policy, permission regression tests. Preserve compatible public routes.
3. **P1c: Marketplace containment/integrity** — validated inputs/prices, unique cart lines and atomic updates, atomic/idempotent unpaid order creation, immutable snapshots and safe deletion, explicit fee disclosure/rounding; keep any live-payment capability disabled. Migrate existing records non-destructively and test failure rollback/concurrent checkout on PostgreSQL. No payment integration.
4. **P2a: property/authority schema and admin** — explicit rentable inventory, roles/authority review, private evidence storage, moderation transitions and audit. Tests deny unverified publication and cross-owner changes.
5. **P2b: media and discovery API** — upload quarantine/validation, approved-listing reads, school/area/price-period/availability filters, saved listings and pagination; private-address and media access tests.
6. **P3: mobile frontend vertical slices** — authentication, search/detail, verification/listing editor, tenant and representative dashboards; accessibility/mobile/slow-network E2E tests.
7. **P4a: viewings and rental offers** — appointment capacity, rental holds, immutable fee snapshots, notifications/outbox; real PostgreSQL concurrency tests.
8. **P4b: agreement sandbox** — versioned demonstration documents, required signatories and mock adapter; integrity/download authorization tests; binding mode unavailable pending counsel/provider gates.
9. **P5: protected-payment/dispute sandbox** — provider-neutral mocks, handover, event authentication/replay/out-of-order tests, reconciliation, release/refund exclusion, dispute freeze and staff audit. No real money or real signing invitations.
10. **P6: separately approved commercial work** — legal/provider contracts, production integrations/certification, security and recovery testing, operating policies, then explicit deployment/live-payment approval.
11. **P7: Marketplace expansion** — only after rentals stabilize, with separate commercial and customer-protection policies.

Each PR includes focused changes, API/migration compatibility notes, actual test results, rollback and manual checks. Security and integrity fixes are prerequisites to a user-facing pilot, not deferred to commercial launch. No new rental functionality is bundled into Phase 1.

## Proposed first implementation phase for approval

Approve P1a–P1c only: secure and stabilize the inherited backend, adopt UniHome branding, preserve migrations/API compatibility and add meaningful CI/regression tests. Exit criteria: cross-account writes blocked; weak/invalid inputs rejected before writes; checkout failure leaves no partial state; immutable historical lines survive source deletion; production settings fail closed; migration checks and relevant regression suite pass. Checkout stays unpaid order creation, without live payment processing. Any breaking route/fee change gets an explicit migration decision.

Before implementation, confirm the destination repository: the audited upstream is `victor-law-create/learning`, while the current configured UniHome checkout belongs to `AnthonyDev-001/UniHome`. Approve use of the latter as the implementation destination or specify another controlled fork. Publishing/pushing is not authorized by this audit.

The next decision is approval or requested changes to this architecture and Phase 1 scope. City/provider/legal selections can proceed independently; they do not block foundational security fixes, but remain mandatory before their dependent features and commercial launch.
