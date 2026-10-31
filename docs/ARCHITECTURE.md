# UniHome architecture

Phase 0 architecture approved; commercial/legal/provider policies remain unresolved.

Use a modular Django/DRF monolith, PostgreSQL for deployed/integration data and versioned `/api/v1/` rental APIs. Preserve legacy account, feed and Marketplace routes and migration history. Keep built-in User initially; new relations use the configured user model and roles become capabilities, allowing one person to be tenant and landlord. Never use social Post or Marketplace carts as canonical rental records.

Planned domains: properties (Property, rentable Unit/Room/Bed, ListingRevision, MediaAsset, Amenity, SavedListing); verification (Case, private DocumentReference, property-specific Authority and ReviewDecision); viewings (Slot, Appointment, Attendance); rentals (Application, immutable OfferVersion/ChargeLine, BookingHold, Occupancy, Handover); agreements (jurisdiction-approved TemplateVersion, AgreementVersion, Signatory, SigningSession, immutable Artifact); payments (provider references, unique events, reconciliation, release/refund instructions); disputes (Case, Evidence, Decision, Appeal); audit and notifications/outbox.

Transitions belong in transactional services; serializers validate input, scoped querysets/object permissions protect records and DB constraints preserve invariants. PostgreSQL locks/exclusion constraints must prevent overlaps across rentable parent/child units. Distinguish viewing capacity from occupancy. Immutable offer/fee/policy snapshots and signed artifacts preserve historical commitments. Use UTC storage, Lagos display and Decimal NGN amounts with explicit billing periods.

Frontend proposal: mobile-first Next.js/React/TypeScript, list-first discovery, explicit rent-period and full-cost display, lazy video, accessible forms, tenant/representative dashboards; Django admin for staff initially. Introduce typed OpenAPI contracts. Same-origin browser sessions or BFF-managed HttpOnly cookies require explicit CSRF/auth design before implementation; existing JWT clients remain supported. No frontend has been built in Phase 1.

Public approved media derivatives and private identity/contracts use separate storage/access policies. Queue/outbox workers are added when asynchronous workflows begin. Signing, financial and notification vendors sit behind adapters; mock/pilot behavior must be clearly distinguished from commercial behavior. No microservices or in-house custodial wallet is proposed.

See [Phase 0 audit](PHASE_0_AUDIT.md) for the complete proposed model, endpoint inventory, threat assessment and PR plan. Phase 1 implementation details and limitations are recorded in [review notes](PHASE_1_REVIEW.md).
