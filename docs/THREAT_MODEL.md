# UniHome threat model

Assets: credentials, identity evidence, exact property location, rental terms, signed records, payment references, handover/dispute evidence and privileged audit history.

Trust boundaries: untrusted browsers/uploads, Django API, database, private/public storage, staff interfaces, asynchronous workers and contracted external providers.

| Threat | Phase 1 control | Required later control |
|---|---|---|
| Cross-account writes | Post object authorization and own-cart scoping; regression tests | Permission matrix across each rental/file endpoint |
| Account takeover/abuse | Password validation, throttled login/registration/recovery, short access lifetime, refresh rotation/blacklist, password-change revocation | Shared cache/edge controls, verified contacts, frontend session policy; async recovery to reduce timing leakage |
| Partial/duplicate checkout | Atomic transaction, locked cart/products, idempotency keys and PostgreSQL race tests | Separate rental occupancy constraints and provider-specific idempotency |
| Lost historical purchase evidence | Snapshotted descriptions/prices, nullable source link, protected order user, read-only order admin | Approved retention/anonymization, tamper-evident business audit/export |
| Insecure deployment defaults | Mandatory private secret, explicit hosts, DEBUG off and secure transport/cookies by default | Ingress validation, secure infrastructure, monitoring and backup/restore exercises |
| Malicious media/private evidence exposure | Image type/size validation; no production upload routes supplied | Quarantine/scanning, metadata stripping, private authorized downloads, separate storage policies |
| Fraudulent property authority / approval bypass | No rental publishing endpoint exists yet | Distinct identity/property authority review, revocation and audited listing transitions |
| Signed-term tampering | No signing workflow enabled | Immutable versions/hash/provider evidence, legal signatory controls |
| Forged/replayed financial events/staff abuse | No live payment or release integration exists | Verified callbacks, reconciliation, unique events, dual control, dispute freeze and append-only audit |

Development credentials in CI/container commands are test-only. Never deploy supplied example keys. The inherited public fallback secret was removed; any prior deployment using it requires secret rotation and session/token invalidation. No such deployment was observed.

These controls do not establish legal compliance, escrow authority or production readiness. See PRD external launch gates.
