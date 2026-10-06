# SOLVO Roadmap

This is the only project document that may contain future capabilities. Complete steps in order and keep each step independently reviewable. A step is done only when its checks and documentation pass.

## MVP delivery steps

### Step 0 — Foundation (COMPLETED)

- Freeze product scope and vocabulary.
- Record architecture and visual system.
- Establish repository guidance and safe configuration examples.
- Add no application code and no AWS implementation.

Exit: the requested foundation files exist and agree on roles, flows, values, scope, and visual tokens.

### Step 1 — Repository and local toolchain

Status: MATERIALLY DELIVERED — GAP. The remaining audit covers the full formatter/linter/type-check contract and the original local container-orchestration exit criterion.

- Create frontend/backend/database/infrastructure structure.
- Configure React + TypeScript, FastAPI + Pydantic, PostgreSQL, formatting, linting, typing, and tests.
- Add local container orchestration and health checks.

Exit: empty application shells and quality checks run locally.

### Step 2 — Domain and database

Status: COMPLETED. Neon migrations are applied through `20260930_0005`; the demo seed provides 13 categories and 52 technicians (four per category).

- Implement ODL model, exact controlled values, database-managed categories, users/roles, teams, ordered technicians/team lead, assignment attempts, reminders, and event history.
- Add migrations and deterministic demo seed data.
- Unit-test transitions, routing order, refusal with optional notes, and invalid/repeated actions.

Exit: domain tests and database migrations pass; no provider dependency is required.

### Step 3 — Core REST API

Status: MATERIALLY DELIVERED — GAP. MVP authentication/authorization and versioned API contracts remain explicit gaps; idempotency and integration-test exit evidence still require audit.

- Implement simple MVP authentication/authorization and versioned contracts.
- Implement categories, ODL CRUD/query, draft confirmation, reminders, history, routing commands, accept/refuse, fulfillment, closure, and cancellation.
- Add idempotency and transaction-level integration tests.

Exit: the complete deterministic workflow is operable through API tests.

### Step 4 — Deterministic local providers

Status: COMPLETED FOR PUBLIC DEMO. Retain the mock/local providers: deployed real adapters use Groq for text extraction (`openai/gpt-oss-120b`) and audio transcription (`whisper-large-v3-turbo`), plus Telegram Bot API for notifications.

- Implement fake AI interpretation, transcription, object storage, and technician notification behind provider ports.
- Delivered: generic NotificationProvider, network-free mock and Telegram Bot API adapter with signed technician links. Production/public-demo notification configuration remains server-side; no chat IDs are exposed to the frontend.
- Status note: Cloudflare Quick Tunnel was temporary development/demo access and is no longer the public-demo architecture.
- Test failure/retry and provider contracts.

Exit: the end-to-end backend demo works offline with repeatable outputs.

### Step 5 — Requester and technician interfaces

Status: COMPLETED.

- Build text/audio intake, processing, editable draft, confirmation, state/reminder view.
- Build the tokenized, touch-friendly technician page for accept/refuse and fulfillment.
- Apply the design system and accessibility requirements.

Exit: requester-to-technician flow works locally on desktop and smartphone viewport.

### Step 6 — Operator Control Center and real time

Status: COMPLETED FOR SINGLE-INSTANCE MVP. The public frontend is hosted at `https://solvo-frontend.onrender.com`; its backend is a Render Web Service with Neon PostgreSQL. This is a public demo, not a production deployment.

- Delivered operator slice: ODL edit/delete, separate notes with atomic history/realtime, Dashboard/list quick reminders, and technician contact editing with routing fields read-only.
- Delivered: private per-technician Telegram binding through signed, expiring (currently 15-minute) bot deep links and an authenticated webhook. The Tecnici page exposes “Collega Telegram”; one Telegram account/chat cannot bind to multiple technicians, `telegram_chat_id` remains server-side, and the frontend receives only `telegram_linked`. The demo fallback remains for unlinked technicians; there is no public unlink UI.
- Build the reference-style sidebar, header/search, summary cards, recent/all ODL table, filters, detail/history, operator actions, and urgent people-risk call treatment.
- Delivered: single-instance in-memory WebSocket updates after commit, Dashboard/detail refetch, and reconnect with backoff.

Exit: technician actions update the Control Center without refresh; no SLA or "tempo aperto" appears.

Verified public E2E: ODL creation → assignment → technician 1 rejection → escalation → technician 2 rejection → escalation → technician 3 → external Telegram notification → signed technician link → accept → `APERTO` → `IN_CORSO`. WebSocket realtime remains in-memory and single-instance; horizontal fan-out would require Redis/shared pub-sub.

### Step 7 — MVP hardening and demo

Status: CURRENT. Immediate queue: readiness audit against these exit criteria; final automated E2E coverage; Step 3 authentication/authorization/security decision; security and token/log-redaction review; reset/reseed procedure including Telegram bindings; public-demo empty/error/loading/responsive polish; repeatable 2–3 minute demo script; final lint/type/test/build gates; and documentation polish.

- Add core end-to-end tests, authorization/security checks, upload limits, logging redaction, empty/error/loading states, responsive polish, and demo reset/seed tooling.
- Document a repeatable 2–3 minute demo and run all quality gates.

Exit: a clean checkout can run and demonstrate the entire local MVP reliably; the public demo is demonstrable without being represented as production.

### Step 8 — External integrations and AWS deployment (deferred)

Status: DEFERRED. AWS deployment is not the current public demo.

- The audio transcription port now has a local mock; a future Amazon Transcribe adapter must preserve temporary-data handling, validated transcripts and explicit draft confirmation.
- Replace local providers with S3 audio, Amazon Transcribe (`it-IT`), Amazon Bedrock structured extraction, adapters. Telegram Bot API is already delivered for the MVP/demo behind the generic notification port.
- For text extraction, target a low-cost Claude Haiku-class model on Bedrock behind the existing AIProvider interface. Select the model/region at implementation time; preserve output validation, database category resolution, local mock tests, and explicit user confirmation. Do not grant the model database or workflow tools.
- Deploy the static frontend through S3/CloudFront, one Dockerized FastAPI/WebSocket backend on EC2, and PostgreSQL on RDS.
- Configure least-privilege IAM, Secrets Manager, CloudWatch, HTTPS, backups, and AWS Budgets.
- Retain local fakes and provider contract tests.

Exit: the same workflow runs in the reference cloud topology with documented teardown and cost controls.

## Future capabilities (not MVP)

- Direct telephone intake with Amazon Connect and streaming transcription.
- Horizontal backend scaling behind an Application Load Balancer, including WebSocket upgrade support, connection/idle-timeout handling and draining, belongs to future AWS architecture.
- Multi-Availability-Zone compute and stronger disaster recovery.
- Multiple backend workers/instances require shared pub/sub such as Redis/ElastiCache for WebSocket fan-out; the delivered in-memory manager cannot synchronize them.
- Event-driven processing with SQS/EventBridge.
- Selective serverless components with API Gateway/Lambda where justified.
- Enterprise authentication with Cognito, MFA, and more granular RBAC.
- Optional enterprise notification channels beyond the Telegram private-chat binding.
- Authenticated technician mobile access.
- Reliable notification delivery, durable retry queues and delivery reconciliation.
- Optional enterprise notification alternatives based on production requirements.
- Fault photo/video attachments and richer intervention history.
- Analytics for categories, acceptance behavior, refusals, reminders, and team workload.
- Production privacy controls: configurable retention, deletion workflows, consent/policy surfaces, encryption governance, and data minimization.
- Expanded production observability with metrics, tracing, alerting, and audit export.


- Production deletion evolution should consider archive/soft-delete and audit retention; the MVP physically deletes ODLs and dependent records.
