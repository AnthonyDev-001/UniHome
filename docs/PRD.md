> Product name normalized to UniHome. Original draft retained in the supplied attachment. Phase 0 architecture was approved; unresolved business/legal/provider decisions remain proposals. Baseline observations describe the pre-Phase-1 audit, not the current implementation.

# UniHome — Product Requirements Document (PRD)

**Status:** Draft for founder review, engineering planning, and Nigerian legal/payment-provider assessment  
**Version:** 1.0 — 28 October 2026  
**Starting repository:** https://github.com/victor-law-create/learning  
**Product scope:** Student lodges and long-term residential rentals in Nigeria  
**Working proposition:** Find it. Verify it. Rent with confidence.

## 1. Purpose and product thesis

UniHome is a mobile-friendly accommodation marketplace connecting prospective tenants to verified landlords and authorized agents. Tenants can browse accurate listings with photos and videos, schedule property inspections, review the complete rental cost, execute a properly designed electronic rental agreement, and pay through an appropriately authorized third-party protected-payment arrangement. Fund release or refund is governed by documented handover and dispute conditions.

The existing general Marketplace is **not** merged into the rental listing model. It remains a separate domain and may be launched later after its API permissions and checkout implementation are secured.

### Problem
- False or stale property advertisements, misleading media, and unclear total costs.
- Difficulty verifying that the person advertising can lawfully rent out the property.
- Pressure to pay before inspection or before possession is established.
- Informal agreements and lack of usable evidence when disputes occur.
- Few transparent channels for timely complaints, refunds, and handover verification.

### Success hypothesis
Users will trust and complete more rental transactions when listings, identity/authority, costs, inspection, agreements, payment custody, and handover are transparent and auditable.

## 2. Initial audience and launch assumptions

- **Launch region:** Nigeria, with an initial city/campus cluster to be selected. Do not assume nationwide rollout at launch.
- **Currency:** Nigerian naira (NGN).
- **Tenancy types:** Student accommodation (bed, room, or self-contained unit) and residential rentals of several months or more; no hotel/short-let model in v1.
- **Channels:** Responsive mobile-first website and Django API. Native Android/iOS apps are later possibilities.
- **Main roles:** Visitor, prospective tenant, verified agent, landlord/property owner, moderator/support, administrator, and externally contracted payment/signing providers. Consider an authorized parent/guardian signatory when the tenant lacks legal capacity.
- **Legal/payment qualification:** No production escrow or binding-signature claims until provider contracts and state-specific Nigerian legal requirements have been reviewed.

## 3. Product boundaries

### In scope for the first commercially viable release
1. Registration, login, role requests, account recovery and user profile.
2. Verification workflow for agents/landlords, including proof of authority to list and manual approval; public verification badges must reflect actual approval.
3. Property, unit/room/bed, amenity, pricing, availability, images and video listing management.
4. Moderation and report-listing workflow; unpublished, suspended and unavailable states.
5. Tenant search, filtering, viewing details and video, saved listings, and contact/viewing requests.
6. Inspection scheduling, confirmations, cancellation, and an auditable viewing history.
7. Full fee breakdown and rental offer before document execution.
8. Lawyer-approved, jurisdiction-aware rental agreement workflow, with authenticated multi-party e-signatures and immutable completed copies, after legal validation.
9. Protected-payment integration via an appropriately authorized partner that actually supports conditional funds holding and release; webhook verification, idempotency, reconciliation, refunds, disputes and manual oversight.
10. Handover confirmation with evidence and a contractually defined inspection/dispute window.
11. Tenant, agent, landlord and admin dashboards, notifications, operational logs and support.
12. Automated tests, deployment readiness, privacy safeguards and documentation.

### Outside v1
- Property sale, land sale, title conveyancing, mortgage and loan products.
- Hotel/nightly short-let reservations.
- In-house wallet, internally held customer deposits, unlicensed escrow, arbitrary transfer of money from UniHome's normal business bank account.
- Automated legal determinations or guaranteed court enforceability.
- Open social feed as the primary property-search surface, real estate investment schemes.
- Full general Marketplace relaunch or native mobile apps (preserve existing code and develop separately).
- AI-generated property descriptions or identity decisions without review.

## 4. Actors and permissions

| Actor | Allowed in v1 | Restricted |
|---|---|---|
| Visitor | Browse approved public listings | Cannot book, sign or pay anonymously |
| Tenant | Save, inquire, book viewings, submit application, sign, fund via provider, confirm handover, dispute, download records | Cannot edit other tenants' documents or listings |
| Agent | Apply for verification; manage authorized listings and viewings; respond to applications | Cannot publish until approved or alter someone else's property; cannot self-release escrow |
| Landlord/Owner | Verify property ownership/authority; approve offers, sign, manage handover | Cannot bypass required signatures or payment controls |
| Moderator | Review listings and identity/authority evidence, take down fraud, resolve operational issues | Cannot silently change executed agreements or funds ledger |
| Admin | Manage permissions, audit, compliance workflow and disputes | Sensitive financial actions require strict roles, provider rules and audit |
| Payment partner | Custody, payment processing, release/refund reporting pursuant to contract | UniHome cannot assume it has escrow powers merely because it can collect card payments |

## 5. Functional requirements and acceptance criteria

| ID | Priority | Requirement | Definition of done |
|---|---|---|---|
| ACC-01 | P0 | Secure account creation/login and role-based permissions | Users cannot access or mutate others' records; tested anonymous/tenant/agent/admin access matrix |
| VER-01 | P0 | Verify listing representative and authority | Verification requires reviewable documents and reviewer decision; pending/rejected accounts cannot publish |
| PROP-01 | P0 | Property, unit and availability catalog | Property can contain multiple rooms/beds; each unit has its own price, capacity and availability |
| PROP-02 | P0 | Complete truthful listing | Address/location granularity, rent billing period, deposit, agent/service fees, utilities, facilities, rules, available date, image/video are captured and displayed |
| PROP-03 | P0 | Moderation and changes | Only approved listings appear publicly; agent can update authorized listings; material changes recorded |
| DISC-01 | P0 | Find a relevant rental | Search by location/school, type, price, bedroom/bed type, facilities and availability; results clearly distinguish student vs residential |
| MEDIA-01 | P0 | Video and media | File types/sizes validated, moderated, securely stored and delivered responsively with accessible fallback; videos not trusted merely because they exist |
| VIEW-01 | P0 | Property viewing workflow | Tenant can request time, agent can accept/reject, both receive status, and the record is retained; no double-booking beyond capacity rules |
| OFFER-01 | P0 | Clear rental price | Show base rent, rental period, deposit, agent/service fees, utilities/other disclosed fees, and total payable before signature/payment |
| AGR-01 | P0* | Document creation and signing | Jurisdiction-approved template; exact version and participant roles locked; identity and consent verified; completed PDF/hash/timestamp/provider audit record securely retained |
| PAY-01 | P0* | Protected rent payment | No live collection until contracted suitable funds-holding provider; verified provider events and independent reconciliation determine actual status |
| PAY-02 | P0* | Strict release and refund rules | Release occurs only per signed objective conditions and provider authority; dispute freezes release where supported and legally agreed |
| HAND-01 | P0* | Handover proof | Keys/possession confirmation, agreed checklist and evidence, deadlines, and both parties' recorded acknowledgements |
| DISP-01 | P0* | Dispute handling | Tenant/landlord can report within specified window, attach evidence, view case status, and receive an appeal/escalation path |
| OPS-01 | P0 | Admin moderation and incident response | Review, suspend listings/users, view audit histories and resolve case queues with least-privilege rights |
| SEC-01 | P0 | Production security | Secrets exclusively via environment/secret manager, debug off, secure hosts/CORS/CSRF, upload limits, rate limiting, logging and backups |
| PRIV-01 | P0 | Privacy and record controls | Private ID/docs not publicly exposed; data minimization, retention, access/export/deletion policy and incident response documented |
| TEST-01 | P0 | Automated verification | Permissions, listing validation, availability conflicts, agreement integrity and payment idempotency have passing automated tests |
| MKT-01 | P1 | Maintain general Marketplace | Do not break existing cart/feed APIs; fix insecure API permissions and unsafe checkout before relaunching Marketplace payments |

`P0*` items are **commercial release blockers** but may be simulated or stubbed in a **closed technical pilot** using mock payment providers and clearly nonbinding demonstration documents.

## 6. Main tenant flow (happy path)

1. Tenant browses a verified and approved property with unit-specific pricing, disclosure of fees, availability and video tour.
2. Tenant creates an account and requests a physical or mutually agreed remote inspection. Property verification is distinct from personally inspecting the condition.
3. Agent confirms the viewing; tenant confirms whether to proceed, with an application or offer as needed.
4. Platform displays total cost, parties, terms, start date, deposit, rent period, refund terms and handover conditions.
5. Authorized landlord/agent and tenant (and any required guardian) execute the correct lawyer-approved documents; signed versions cannot be silently changed.
6. Tenant pays through partner-hosted payment flow; UniHome receives verified event and references, not custody of the money by default.
7. Handover takes place with condition checklist, keys/access, date/time, acknowledgements and supporting evidence.
8. Tenant confirms completion or opens a dispute within the agreed window. Provider releases or refunds only when permitted by the contract, applicable law and provider arrangement.
9. Parties receive transaction receipt, completed agreement, handover record and case resolution documentation.

## 7. State machines and safety invariants

### Listing
`DRAFT -> PENDING_REVIEW -> ACTIVE -> RESERVED -> OCCUPIED/UNAVAILABLE` with `REJECTED`, `SUSPENDED`, and `ARCHIVED` as controlled side states. An unverified agent or rejected listing may not become active.

### Rental application
`INQUIRY -> VIEWING_REQUESTED -> VIEWING_COMPLETED -> OFFER_PENDING -> TERMS_ACCEPTED -> AGREEMENT_PENDING -> AGREEMENT_SIGNED -> PAYMENT_PENDING -> FUNDED -> HANDOVER_PENDING -> INSPECTION_WINDOW -> COMPLETED` with `CANCELLED`, `DISPUTED`, `REFUND_PENDING`, and `REFUNDED` as explicit branches. Do not treat this example as a legal mandate; refine with counsel/provider before implementation.

### Non-negotiable invariants
- A property may not be booked or paid for while unavailable or unapproved; prevent concurrent double bookings at the unit level.
- A tenant cannot pay into the protected flow before all required agreement signatures and full cost disclosures are complete.
- A merchant cannot unilaterally initiate payment release; release decisions follow provider controls and contractual terms.
- No side may change a signed agreement; updates create a new version requiring fresh consent/signatures.
- Payment webhooks are signature-verified, idempotent and reconciled with provider records; one event cannot result in duplicate funding/release/refund.
- A filed dispute blocks release where the contracted scheme permits it; no unilateral deletion of disputes or evidence.
- Refund/hold/inspection deadlines must be explicit, fair, lawyer-approved and visible before payment.
- Every privileged action generates an access-controlled audit event.

## 8. Proposed domain/data architecture

Retain the existing Django backend and existing `accounts`, `feed`, and `marketplace` modules wherever practical. **Do not reuse the generic social `Post` record as the canonical rental property listing.** Add distinct domain apps and preserve existing migrations:

- `properties`: Property, Unit, Amenity, PropertyMedia, AvailabilityRule, ListingReview, ListingReport.
- `verification`: VerificationRequest, DocumentReference, OwnershipAuthorization, ReviewDecision.
- `viewings`: ViewingRequest, Appointment, AttendanceRecord.
- `rentals`: RentalApplication, RentalOffer, RentBreakdown, BookingHold, HandoverChecklist.
- `agreements`: AgreementTemplate, AgreementVersion, Signatory, SigningSession, SignedArtifact, SignatureAuditEvent.
- `payments`: PaymentIntent, ProviderTransaction, PaymentEvent, ProtectedFundsCase, ReleaseInstruction, RefundInstruction, ReconciliationRecord.
- `disputes`: Dispute, EvidenceAttachment, Resolution, Appeal.
- `notifications`: NotificationPreference, OutboundMessage, DeliveryStatus.
- `audit`: append-only security and business events.

Physical property address and sensitive identity/contract files should have tiered access. Host media and signed documents using secure object storage or vendors rather than storing raw videos in database rows.

## 9. UX pages (mobile-first)

- Landing / Rentals navigation with two filters: Student Lodges and Long-Term Rentals.
- Search/results (list first; optional map), school/area search, saved homes.
- Property detail with video, gallery, exact fees, amenities, availability, verification status and viewing call-to-action.
- Tenant dashboard: viewings, applications, agreements, protected-payment status, handovers, support.
- Agent/landlord onboarding and verification, listing editor, inquiry/viewing and handover dashboard.
- Agreement review/signing and receipt page; completion/downloadable records.
- Admin: review queue, verification, listings, disputes, case notes, audit and payment reconciliation.
- Distinct Marketplace navigation later; never mix shopping cart products and rental commitments as the same order type.

## 10. Quality, privacy and operations requirements

- Use Django REST Framework and API versioning; preserve public routes until a documented migration is approved.
- PostgreSQL recommended for deployed relational data; SQLite acceptable in local/CI development. Provide non-destructive migration path.
- Frontend recommendation: responsive Next.js/React talking to the existing DRF API (subject to engineering review); design for bandwidth-constrained mobile users, lazy video loading and accessible forms.
- Define ownership and role-based access for every endpoint, including file downloads.
- Use production-ready secrets, HTTPS, secure cookies/session or token storage, anti-CSRF where needed, rate limiting, account recovery and access logs.
- Malware/content validation for uploads, EXIF/privacy review, file retention and secure backups.
- Log document and payment transitions; use verified provider callbacks and a task queue for retryable asynchronous work.
- Write end-to-end tests for verified listing to viewing to signing to sandbox payment to handover and dispute.
- Ensure accessible UI, clear NGN currency formatting, receipts, contact/support and error states.
- Implement privacy by design consistent with Nigeria Data Protection Act 2023; seek local privacy advice for consent/other lawful basis, notices and retention.

## 11. Regulatory/legal launch gates — require expert review

1. **Digital agreements:** Nigerian Evidence Act (as amended in 2023) contains provisions concerning electronic records, electronic/digital signatures and proof. An e-signature is not an automatic guarantee of enforceability. Verify state-specific lease/tenancy formalities, signatory authority, required witnessing, stamping, record authentication and legal capacity. Contracts/templates and procedures must be approved by Nigerian counsel.
2. **Payments:** Evaluate authorized providers and their *specific contractual ability* to hold, conditionally release, refund and dispute funds. Ordinary payment splitting is not escrow. Do not receive and hold customer funds in UniHome's operating account by default.
3. **Property and agent verification:** Validate identity plus legal ownership or documentary authority to market/lease, and any local estate-agent registration obligations.
4. **Privacy:** Verification documents, signatures and transaction data must be handled under Nigeria Data Protection Act 2023. Minimize public identifiers and define deletion/retention rules.
5. **Students under legal age:** Obtain counsel-approved parent/guardian participation or restrict contract execution where users cannot legally enter agreements.
6. **Dispute fairness:** Establish time limits, independent review, appeal and what happens when no one responds, consistent with provider constraints and state law.

Useful starting references: https://www.cbn.gov.ng/PaymentsSystem/PSPs.html ; https://ndpc.gov.ng/resources/ ; https://lawcarenigeria.com/evidence-act-as-amended-by-the-evidence-amendment-act-2023/ ; https://stampduty.gov.ng/services

## 12. Explicit product decisions pending founder review

- First city, campuses and neighborhoods, then expansion.
- Are agents the only publishers or can landlords self-publish after verification?
- Inspection before signing/payment: mandatory for all or optional with stronger remote-inspection protections?
- Rent periods (per bed/room/month/semester/year), deposits, refundable vs non-refundable fees, utility charges and cancellation policy.
- Who signs for the landlord: owner, licensed/authorized agent, or both? Any guardians required?
- Chosen signing provider/verification process and court-proof evidence retention policy.
- Chosen custody/escrow partner and exact release/refund timetable; dispute decision-maker and appeal path.
- Platform revenue model: subscription, verified listings, service fee, or commission; disclose all charges.
- Service SLA, support staffing and dispute operations.
- Whether and when Marketplace is surfaced publicly.

Until these are approved, use configurable business rules and sandbox mock integrations; do not hardcode arbitrary real-world legal/payment deadlines or fee percentages.

## 13. Launch readiness and success measures

**Pilot definition:** Functional listings, verification, viewing and simulated signing/protected payment in a closed sandbox; no claims of live escrow, no collection of live funds through simulated flows.

**Commercial MVP launch requires:** documented legal approvals, an executed suitable provider agreement, signed-document workflow validated by counsel, complete permission and security tests, reconciled live-payment safeguards, support/dispute staffing, privacy policy, logging/backup/recovery and incident procedures.

**Proposed measures:** approved verified properties, percentage of listings with usable video and full fee disclosures, viewing completion rate, agreement completion rate, verified handovers, dispute incidence and resolution time, fraudulent listing reports, support response time, and transaction reconciliation discrepancies. Establish targets after first pilot data.
