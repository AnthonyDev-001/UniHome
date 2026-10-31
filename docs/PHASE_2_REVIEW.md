# Phase 2 — rental catalog and verification review

Branch: `phase-2-properties-verification`, stacked on Phase 1 commit `1578bf6ca044ad95d0ad8e69a651e5281d7abfbe`. Phase 1 remains a dependency, not silently merged into main. No live funds, signing invitations or deployment included.

## Delivered

- Separate properties, independently rentable unit/room/bed inventory, amenities, explicit NGN rent periods and fee disclosures. General Marketplace is untouched.
- Identity/role cases and distinct property-authority cases with private evidence, independent reviewer permissions, optional explicit expiry, rejection, suspension and controlled reopening. Neither role claims nor staff status alone can publish.
- Immutable submitted listing snapshots/hashes, revision checks, moderation queue and suspension controls. Publication requires current representative approvals, an available space and approved photo/video media. Public reads recheck approval/expiry; no stale badge based only on a boolean.
- Material-change withdrawal, preserved suspension, read-only generic admin details, controlled admin review actions, audit events and report/resolution queues. No generic state PATCH, self-review or owner-triggered unsuspension.
- Private local storage outside public media/static; authorized evidence downloads, metadata-only responses, randomized filenames/checksums and no-store delivery. Images are re-encoded without EXIF; MP4 videos are inspected and normalized with ffprobe/ffmpeg, then held for human review. Standard video metadata is removed; content still needs privacy review.
- Availability blocks with non-overlap checks and PostgreSQL locking, current-day availability and date-aware discovery. Actual bookings/reservations are not implemented until Phase 4.
- Additive migrations, developer/API documentation, staff review groups and CI ffmpeg prerequisite. No historical migrations or existing production records were rewritten.

## Review and setup

See [rental API contract](RENTAL_API.md) for every route, payload, state transition, permission rule and resource limit.

1. Install Phase 1 requirements and ffmpeg/ffprobe from a supported OS package source; Python alone is insufficient for video handling. This workspace used ffmpeg/ffprobe 7.1.5. Keep media tooling patched. CI installs the distro package and runs the full suite.
2. Set development/secret/database configuration per README. Set PRIVATE_UPLOAD_ROOT to a private backed-up location outside public web roots. Never serve that directory directly. No cloud storage account or production file-serving configuration was created.
3. Back up an existing database; test migrations on a copy. Run `python manage.py migrate`, then `python manage.py bootstrap_rental_roles`. The group command is additive/idempotent and does not enroll users, grant staff status or change existing permissions.
4. Assign appropriate groups to selected active staff through Django admin. Identity, authority, media, listing and audit permissions are separate. A person may hold more than one group in a closed pilot, but cannot review their own submissions or represented property.
5. Through the API, create a synthetic draft, identity case/evidence, property-authority request/evidence, independent spaces/charges and media. Review identity/authority/media, submit the listing, then approve the exact revision through API or admin actions. Admin review reason is required; listing actions also require the inspected revision.
6. Verify the public detail exposes reviewed facts and full costs while withholding the dedicated exact address, documents and review notes. Modify the price or withdraw authority and verify public detail/media disappear. Test another user's writes and a forged status.

Groups: UniHome identity reviewers, authority reviewers, listing moderators, media reviewers and auditors. Amenity creation is a separate admin permission; existing amenity names are immutable to avoid changing already-reviewed public facts without a listing revision.

## Validation evidence

Python 3.12, patched Phase 1 pins, disposable PostgreSQL 16, temporary private storage and synthetic evidence/media only.

- Full suite: **48 tests passed on PostgreSQL**, including all Phase 1 regressions and three new Phase 2 concurrency cases. Those cases reject overlapping blocks, preserve simultaneous edits/revisions and prove identity suspension racing publication never leaves a public listing.
- SQLite: **48 discovered, 42 passed, 6 explicit PostgreSQL-only skips** (three original checkout races and three inventory/review races).
- Real media fixtures: generated H.264 MP4 is inspected/remuxed and reviewed through the API; title metadata removal is checked. Invalid video, oversized video, absent validator, image EXIF removal and unauthorized file access are covered.
- Admin integration: actual admin approval of a complete synthetic listing, stale-revision rejection, suspension, forbidden generic saves and protected evidence download links. Expanded admin path is additionally checked on PostgreSQL.
- Fresh migrations and inherited legacy migration tests pass. `check`, migration drift checks and `git diff --check` pass. Hosted GitHub Actions is configured; its results must be observed separately and are not inferred from local runs.

The PostgreSQL run caught a test-harness streaming cleanup issue: manually closing a TestCase response triggered connection teardown inside its enclosing transaction. Tests now consume the actual stream through Django's test-client wrapper, verifying the bytes as well as authorization. No assertion or production DB safeguard was disabled.

## Assumptions, boundaries and remaining work

- A draft creator is a manager, not an assertion of legal ownership. Manual authority review must validate the actual documentary relationship. Approved badges explain review scope and do not guarantee title, condition or court enforceability.
- Both agent and landlord cases are supported behind independent manual approval; commercial publisher eligibility, documentary standards, jurisdictional rules and renewal policies still need owner/legal decisions.
- Each property uses one inventory granularity. There are no simultaneously rentable parent rooms and child beds. Multi-level inventory/occupancy and reservation holds must be designed/tested in Phase 4; availability block races do not prove double-booking protection for a future booking flow.
- No tenant-facing frontend, saved homes, viewing appointments, offers, agreements, protected payments, handover or dispute adjudication exists yet. Listing reports are a moderation channel, not a financial/legal dispute process.
- Fixed charges only, with explicit recurrence/refundability; total_first_period is a disclosure calculation, not a binding rental offer. No hidden rental commission or financial policy was introduced.
- No automated KYC/provider verification, malware clearance, legal approval or production cloud-storage integration is claimed. Synchronous media processing is bounded but must move to isolated workers with quotas/scanning before open production uploads. API file delivery is for the closed pilot, without CDN/range optimization.
- Audit/revision records are append-only through supported API/admin/model-instance operations, not tamper-proof against privileged SQL/DB operators. Production needs restricted DB roles, retention policy and protected audit export/storage. File and relational storage need orphan reconciliation and tested backup/restore.
- Existing signup/cart signal coupling and remaining Phase 1 operational limitations are unchanged. No real identity documents should be collected before privacy notices, lawful basis, access/retention rules and secure operational storage are approved.

## Migration and rollback

New 0001 migrations create audit/properties/verification tables only, preserving existing account/feed/Marketplace history. Private-storage import paths are referenced by migrations and must remain importable. No user enrollment occurs on migration.

Before reverting, export new catalog/review/audit records and private files and assess privacy obligations. Reverse migrations drop new tables/data; do not run them blindly after collecting records. Prefer a forward fix. Reverting code also removes the private download API; keep private files inaccessible, rather than publishing their directory to recover access. No migration ran against production and no main merge/deployment was performed.

Next reviewed phase: mobile-first tenant/representative frontend and discovery experience using these APIs. Signing, actual reservations and financial work retain their later gates.
