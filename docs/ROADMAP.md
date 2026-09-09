# SOLVO Roadmap

This is the only project document that may contain future capabilities. Complete steps in order and keep each step independently reviewable. A step is done only when its checks and documentation pass.

## MVP delivery steps

### Step 0 — Foundation (current)

- Freeze product scope and vocabulary.
- Record architecture and visual system.
- Establish repository guidance and safe configuration examples.
- Add no application code and no AWS implementation.

Exit: the requested foundation files exist and agree on roles, flows, values, scope, and visual tokens.

### Step 1 — Repository and local toolchain

- Create frontend/backend/database/infrastructure structure.
- Configure React + TypeScript, FastAPI + Pydantic, PostgreSQL, formatting, linting, typing, and tests.
- Add local container orchestration and health checks.

Exit: empty application shells and quality checks run locally.

### Step 2 — Domain and database

- Implement ODL model, exact controlled values, database-managed categories, users/roles, teams, ordered technicians/team lead, assignment attempts, reminders, and event history.
- Add migrations and deterministic demo seed data.
- Unit-test transitions, routing order, refusal with optional notes, and invalid/repeated actions.

Exit: domain tests and database migrations pass; no provider dependency is required.

### Step 3 — Core REST API

- Implement simple MVP authentication/authorization and versioned contracts.
- Implement categories, ODL CRUD/query, draft confirmation, reminders, history, routing commands, accept/refuse, fulfillment, closure, and cancellation.
- Add idempotency and transaction-level integration tests.

Exit: the complete deterministic workflow is operable through API tests.

### Step 4 — Deterministic local providers

- Implement fake AI interpretation, transcription, object storage, and technician notification behind provider ports.
- Delivered: generic NotificationProvider, network-free mock and explicitly triggered Telegram Bot API adapter with signed technician links exposed inline. All demo notifications use server-side TELEGRAM_DEMO_CHAT_ID without a schema change.
- Delivered demo instructions: Cloudflare Quick Tunnel supplies a temporary phone-accessible frontend URL; this is not production deployment.
- Test failure/retry and provider contracts.

Exit: the end-to-end backend demo works offline with repeatable outputs.

### Step 5 — Requester and technician interfaces

- Build text/audio intake, processing, editable draft, confirmation, state/reminder view.
- Build the tokenized, touch-friendly technician page for accept/refuse and fulfillment.
- Apply the design system and accessibility requirements.

Exit: requester-to-technician flow works locally on desktop and smartphone viewport.

### Step 6 — Operator Control Center and real time

- Build the reference-style sidebar, header/search, summary cards, recent/all ODL table, filters, detail/history, operator actions, and urgent people-risk call treatment.
- Delivered: single-instance in-memory WebSocket updates after commit, Dashboard/detail refetch, and reconnect with backoff.

Exit: technician actions update the Control Center without refresh; no SLA or "tempo aperto" appears.

### Step 7 — MVP hardening and demo

- Add core end-to-end tests, authorization/security checks, upload limits, logging redaction, empty/error/loading states, responsive polish, and demo reset/seed tooling.
- Document a repeatable 2–3 minute demo and run all quality gates.

Exit: a clean checkout can run and demonstrate the entire local MVP reliably.

### Step 8 — External integrations and AWS deployment (deferred)

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
- Associate each technician with a verified notification destination/user or an optional enterprise notification channel; replace the shared TELEGRAM_DEMO_CHAT_ID shortcut.
- Authenticated technician mobile access.
- Reliable notification delivery, durable retry queues and delivery reconciliation.
- Optional enterprise notification alternatives based on production requirements.
- Fault photo/video attachments and richer intervention history.
- Analytics for categories, acceptance behavior, refusals, reminders, and team workload.
- Production privacy controls: configurable retention, deletion workflows, consent/policy surfaces, encryption governance, and data minimization.
- Expanded production observability with metrics, tracing, alerting, and audit export.

