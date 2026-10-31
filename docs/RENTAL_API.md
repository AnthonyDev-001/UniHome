# UniHome rental API — Phase 2

New endpoints use `/api/v1/`. Existing `/api/accounts/`, `/api/posts/` and Marketplace routes are unchanged. Authenticate private endpoints with `Authorization: Bearer <access-token>` from the existing login endpoint. Lists use `{count, next, previous, results}` with 25 records per page. IDs are UUIDs except amenity IDs. All supplied data in development must be synthetic.

## Endpoint inventory

| Path below /api/v1/ | Methods | Access and purpose |
|---|---|---|
| properties/ | GET | Public: only active, current-revision listings with current publisher identity/property authority |
| properties/{id}/ | GET | Public approved listing; no dedicated exact-address field, identities or review notes |
| properties/{id}/report/ | POST | Authenticated; reason and details, private report |
| amenities/ | GET | Public reference catalog |
| management/properties/ | GET, POST | Own/authorized managed properties; listing reviewers may read all |
| management/properties/{id}/ | GET, PUT, PATCH | Managed content; reviewer privileges alone do not grant editing rights |
| management/properties/{id}/submit/ | POST | Representative with current identity and property-authority approvals |
| management/properties/{id}/review/ | POST | Staff + review_listing; expected_revision, decision and reason required |
| management/properties/{id}/withdraw/ | POST | Representative: status UNAVAILABLE or ARCHIVED; cannot unsuspend |
| management/properties/{id}/revisions/ | GET | Authorized manager/reviewer; submission number, checksum, time; full private snapshots in authorized admin |
| units/ and units/{id}/ | GET, POST / GET, PUT, PATCH | Managed property spaces; no destructive delete |
| units/{id}/blocks/ | GET, POST | Managed availability; POST starts_on, exclusive ends_on, reason |
| units/{id}/cancel-block/ | POST | Managed; block_id, cancellation preserved as a record |
| charges/ and charges/{id}/ | GET, POST / GET, PUT, PATCH | Managed disclosed fees, immutable parent unit |
| media/ and media/{id}/ | GET, POST / GET | Managed media; staff media/listing reviewers can inspect all; multipart uploads only |
| media/{id}/review/ | POST | Staff + review_media, independent of uploader/property parties |
| media/{id}/file/ | GET | Public only for approved media on a currently public listing; authorized manager/reviewer can inspect private files |
| verification/cases/ and cases/{id}/ | GET, POST / GET | Own identity/role requests; identity reviewers can read their queue |
| verification/cases/{id}/submit/ | POST | Applicant, evidence required |
| verification/cases/{id}/review/ | POST | Staff + review_verification; no self-review |
| verification/authorities/ and authorities/{id}/ | GET, POST / GET | Own property-authority requests; authority reviewers can read their queue |
| verification/authorities/{id}/submit/ | POST | Representative, current identity approval and evidence required |
| verification/authorities/{id}/review/ | POST | Staff + review_authority; no self-review |
| verification/documents/ | GET, POST | Own evidence or corresponding reviewer permission; multipart, exactly one case/authority ID |
| verification/documents/{id}/ | GET | Authorized metadata only; no storage URL/path |
| verification/documents/{id}/file/ | GET | Authorized attachment download, no-store; audited; never public |
| reports/ and reports/{id}/ | GET | Reporter sees own reports; listing moderators see queue |
| reports/{id}/resolve/ | POST | Staff + review_listing, reason required, no party self-resolution |
| audit/ and audit/{id}/ | GET | Staff + view_auditevent; no create/update/delete API |

Django sessions are additionally accepted by document/media endpoints so authorized staff can inspect files from admin. CSRF remains enabled for session-authenticated writes. Review permissions require active staff status **and** the stated permission; staff status alone is insufficient. Model admin screens expose controlled review actions and readonly details; generic admin saves/deletes are forbidden. Admin listing decisions require the exact revision number the moderator inspected.

## Example payloads

Create an identity case with `{"role": "AGENT"}` or `{"role": "LANDLORD"}`. This requests a review; it never grants staff rights or an automatic badge. Upload evidence with multipart `case=<uuid>` and `file=<synthetic PDF/image>`, then submit. Case/authority decisions accept:

```json
{"decision": "APPROVED", "reason": "Documentary checks completed", "expires_at": "2027-01-31T23:00:00Z"}
```

Expiry is optional because no commercial renewal policy is approved; staff can set an explicit deadline. It is never inferred from an arbitrary legal validity period. Other decisions: REJECTED for pending requests, SUSPENDED for approved requests, REOPEN for suspended/expired requests. Reopening returns to draft, never directly to approval. Approved/submitted evidence cannot be overwritten; rejected/draft requests accept additional documents. A role may be requested once per applicant; rejected or expired cases are reused through controlled transitions rather than duplicated.

Create a property under `management/properties/`:

```json
{
  "title": "Example campus lodge",
  "description": "Synthetic development listing",
  "category": "STUDENT",
  "state": "Enugu", "city": "Nsukka", "area": "Example area",
  "campus": "Example campus",
  "private_address": "Synthetic exact address — never public",
  "rules": "Example house rules",
  "amenities": []
}
```

The creator is the draft's manager, **not proof of legal ownership**. To request documentary authority, POST `{ "property": "<uuid>", "verification": "<approved-own-case-uuid>" }` to `verification/authorities/`, add authority evidence, submit and obtain independent approval. Requests may reference one's own/authorized drafts or a public property. Another user cannot see or request authority over an inaccessible private draft. An approved additional representative can manage that property; review must establish the actual authority from evidence. No automatic ownership transfer is implemented.

Create a space under `units/`:

```json
{
  "property": "<uuid>", "label": "Room A", "kind": "ROOM", "capacity": 1,
  "rent": "150000.00", "billing_period": "YEAR", "available_from": "2027-01-01"
}
```

Kinds: UNIT, ROOM, BED. Each is an independently rentable inventory record, not a container of other rentable records. All spaces in one property must use the same granularity; a whole room and its beds cannot both be offered in the same property. BED capacity must be one; room/unit capacity describes occupants of that one space, not inventory to sell independently. Hierarchical inventory and actual reservation/lease workflows remain Phase 4. Preventing duplicate claims across separate property records also requires documentary moderation.

Disclose charges under `charges/`:

```json
{
  "unit": "<uuid>", "kind": "DEPOSIT", "label": "Refundable deposit",
  "amount": "20000.00", "refundable": true, "recurring": false
}
```

Kinds: DEPOSIT, AGENT, SERVICE, UTILITY, OTHER. Both refundability and recurrence must be explicit. Recurring means one charge per stated rent period; no implicit monthly conversion of annual/semester figures. `total_first_period` is rent plus each disclosed charge once, not a complete multi-period rental offer or an approved contract. Only fixed charges are modeled here. All rental money is NGN; there is no inherited 12% rental fee or payment request.

Upload an IMAGE or VIDEO under `media/` with multipart property, kind, caption and file. Images are decoded/re-encoded, orientation normalized and EXIF removed; supported input JPEG/PNG/WebP, single frame, at most 5 MiB/20 megapixels. Videos require ffprobe/ffmpeg, at most 50 MiB, 180 seconds and 3840×2160; H.264 MP4 with optional AAC audio. Input is parsed as MOV/MP4 with external data references disabled and network protocols excluded; normalization remuxes only audio/video streams and removes standard container/stream metadata and chapters. Review remains mandatory. These checks are not malware clearance, frame redaction or proof of current property condition.

Media decisions accept `{"decision":"APPROVED","reason":"Visual/content checks completed"}` or REJECTED. Files cannot be replaced in place. A listing requires an approved image and video before submission. Listing approval additionally needs:

```json
{"decision": "APPROVED", "reason": "Exact listing revision reviewed", "expected_revision": 7}
```

The server checks the immutable submission checksum, representative authority and revision before publishing. Material edits, price/charge changes, media uploads/reviews and availability changes invalidate publication. A newly reviewed asset on an active/pending listing conservatively suspends that listing; staff must reopen it before a fresh submission. Neither changing content nor withdrawing to UNAVAILABLE can lift a suspension. ARCHIVED records cannot be edited or reactivated by these APIs.

## Discovery and availability

Public filters: category, city, area, campus, kind, billing_period, min_rent, max_rent and available_on. Any price bound requires billing_period; different billing periods are never silently compared. Space filters apply to the **same space**. Prices filter base rent; fee disclosure remains on each result. Filtered properties include their full reviewed space catalog so clients must honor each space's availability/status. Exact addresses must also be excluded from free-text public descriptions by moderation; the serializer only guarantees omission of the dedicated private field.

Availability blocks use half-open intervals `[starts_on, ends_on)`; adjacent intervals are allowed. Creation serializes on the representative/property/space and rejects overlap. Inactive/occupied spaces or dates before available_from are not available. `available_today` uses Lagos's UTC+1 date. Availability is informational inventory state, **not an actual booking**. There is no reservation/payment endpoint in this phase. Phase 4 must add tenant eligibility, booking holds, period constraints and transaction-level booking tests before accepting reservations.

## Storage and operational limits

PRIVATE_UPLOAD_ROOT defaults to the ignored `private_uploads/` directory outside backend media/static. Do not mount it behind nginx/static/CDN/public bucket delivery. Startup rejects overlap with public media/static roots. Files have random names, owner-only filesystem modes, checksums and authorized per-request delivery. Evidence is forced to attachment/octet-stream with no-store/nosniff. Media has no stable public storage URL and public delivery checks listing eligibility again, including expired/suspended identity/authority.

Technical closed-pilot limits: 100 independently rentable spaces, 20 media files per property, 20 fixed charges per space, 10 evidence documents per request. These are resource limits, not legal/rent policies. Records and evidence are retained; there is no destructive deletion API. Establish privacy retention/erasure exceptions before collecting real documents. Upload-to-filesystem and DB commits cannot be perfectly atomic: normal write failures clean up new files, but crashes/outer-transaction failures may leave private orphans. A production storage/retention/sweeper pipeline, malware scanning, isolated media workers, byte-range/CDN delivery, quotas and backup/restore remain release requirements.
