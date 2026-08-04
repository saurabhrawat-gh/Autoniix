# Gateway v2 — Unimplemented Endpoints

The following endpoints are planned but not yet implemented. They were previously stubbed with 501 responses.

## Experiments
- `GET /api/v2/experiments` — List experiments
- `POST /api/v2/experiments` — Create experiment
- `GET /api/v2/experiments/:id` — Get experiment details
- `PATCH /api/v2/experiments/:id` — Update experiment
- `DELETE /api/v2/experiments/:id` — Delete experiment

## Finishing
- `GET /api/v2/finishing` — List finishing jobs
- `POST /api/v2/finishing` — Create finishing job
- `GET /api/v2/finishing/:id` — Get finishing job status

## Feature Flags
- `GET /api/v2/flags` — List feature flags
- `POST /api/v2/flags` — Create feature flag
- `PATCH /api/v2/flags/:id` — Update feature flag

## Library
- `GET /api/v2/library` — List library items
- `POST /api/v2/library` — Add library item
- `GET /api/v2/library/:id` — Get library item
- `DELETE /api/v2/library/:id` — Delete library item

## Lookup Values
- `GET /api/v2/lookup-values` — List lookup values
- `POST /api/v2/lookup-values` — Create lookup value
- `PATCH /api/v2/lookup-values/:id` — Update lookup value
- `DELETE /api/v2/lookup-values/:id` — Delete lookup value

## Providers
- `GET /api/v2/providers` — List providers
- `POST /api/v2/providers` — Create provider
- `GET /api/v2/providers/:id` — Get provider details
- `PATCH /api/v2/providers/:id` — Update provider
- `DELETE /api/v2/providers/:id` — Delete provider

## Provider Chains
- `GET /api/v2/provider-chains` — List provider chains
- `POST /api/v2/provider-chains` — Create provider chain
- `GET /api/v2/provider-chains/:id` — Get provider chain
- `PATCH /api/v2/provider-chains/:id` — Update provider chain
- `DELETE /api/v2/provider-chains/:id` — Delete provider chain

## Review
- `GET /api/v2/review` — List items pending review
- `POST /api/v2/review/:id/approve` — Approve item
- `POST /api/v2/review/:id/reject` — Reject item

## System
- `GET /api/v2/system/health` — System health check
- `GET /api/v2/system/stats` — System statistics
- `GET /api/v2/system/config` — System configuration

## Voice
- `GET /api/v2/voice` — List voice jobs
- `POST /api/v2/voice` — Create voice job
- `GET /api/v2/voice/:id` — Get voice job status
- `PATCH /api/v2/voice/:id` — Update voice job
- `DELETE /api/v2/voice/:id` — Delete voice job

## Proxy Operations
- `POST /api/v2/proxy/trigger` — Trigger proxy operation
- `POST /api/v2/proxy/clone` — Clone proxy
- `POST /api/v2/proxy/pause` — Pause proxy
- `POST /api/v2/proxy/resume` — Resume proxy
- `POST /api/v2/proxy/stop` — Stop proxy
