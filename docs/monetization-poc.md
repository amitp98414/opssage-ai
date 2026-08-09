# OpsSage Monetization POC

This POC adds a small sponsored-content and revenue-ledger layer to OpsSage AI.

## Scope

- Advertiser campaign creation
- Highest-bid campaign selection
- Explicit `Sponsored` disclosure
- Impression and click event tracking
- Idempotent event IDs
- SHA-256 hashing of session identifiers before persistence
- Simulated CPM billing
- 70/30 developer/platform revenue split for the POC
- Earnings aggregation endpoint

## Endpoints

- `GET /monetization/health`
- `POST /monetization/campaigns`
- `GET /monetization/campaigns`
- `GET /monetization/ad` with `X-Session-ID`
- `POST /monetization/events`
- `GET /monetization/earnings`

## Local test flow

1. Start the FastAPI backend.
2. Open `/docs`.
3. Create a campaign with a small test budget.
4. Request `/monetization/ad` with an `X-Session-ID` header of at least 16 characters.
5. Send the returned `event_id` to `/monetization/events` as an `impression`.
6. Query `/monetization/earnings`.

## Security boundary

This is a development POC only. Campaign creation is intentionally simple and must not be exposed as a public advertiser API yet. Before production, add authenticated advertiser accounts, campaign review/moderation, payment authorization, signed event tokens, replay protection, rate limiting, fraud detection, consent/privacy controls, audit logs, and a versioned database migration system.

## Revenue boundary

No real advertiser is charged and no real payout is made by this POC. Billing is simulated in the database so the economics can be tested safely before payment integration.
