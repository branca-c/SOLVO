# SOLVO Architecture

## 1. Architecture goal

Use a modular monolith with explicit boundaries. This keeps the MVP fast to build and easy to demonstrate while preserving seams for the integrations described in the technical guide. The first runnable system is local-first; no AWS resources are implemented at this foundation stage.

```text
Requester portal ─┐
Operator dashboard ├─ REST / WebSocket ─ FastAPI modular monolith ─ PostgreSQL
Technician mobile ─┘                         │
                              provider interfaces (local fakes first)
                              ├─ AI / transcription
                              ├─ object storage
                              └─ technician notification
```

## 2. Intended repository shape

```text
solvo/
├── frontend/              # React + TypeScript application (later)
├── backend/               # FastAPI + Python application (later)
│   ├── api/               # HTTP/WebSocket transport
│   ├── domain/            # Entities, value objects, transitions, routing
│   ├── services/          # Application use cases and provider ports
│   ├── repositories/      # Persistence adapters
│   └── tests/
├── database/              # Migrations and deterministic seed data (later)
├── infrastructure/        # Local containers first; cloud work deferred
├── docs/
└── README.md
```

Directories are created only when their implementation step starts.

## 3. Module boundaries

| Module | Owns | Must not own |
|---|---|---|
| Domain | ODL rules, status transitions, assignment sequence, controlled values | HTTP, SQL, provider SDKs |
| Application services | Use-case orchestration, transactions, idempotency, authorization decisions | UI rendering, infrastructure configuration |
| API | REST contracts, WebSocket sessions, validation/error mapping | Business-rule duplication |
| Repositories | PostgreSQL mapping and queries | Workflow decisions |
| Providers | AI, transcription, storage, notification adapters | Database writes or status transitions |
| Frontend | Role surfaces, forms, view state, accessible presentation | Authoritative workflow decisions |

Dependencies point inward: adapters depend on application/domain contracts. Provider-specific payloads do not cross into the domain.

## 4. Core persistence model

The initial schema should model these concepts rather than compressing them into one table:

- `users`: identity and one MVP role.
- `categories`: database-managed category records with active/order fields.
- `teams`: category routing ownership and team-lead contact.
- `technicians`: technician contact and availability needed by routing.
- `team_members`: ordered Technician 1–3 membership plus team lead.
- `work_orders`: required ODL fields, exact status/priority/origin values, people-risk flag, current assignment reference, timestamps, and optimistic version.
- `assignment_attempts`: candidate, order, token digest, sent/responded timestamps, and outcome.
- `reminders`: one row per reminder with server timestamp and actor.
- `work_order_events`: append-only audit history.
- `audio_assets`: storage reference and transcription lifecycle, without putting audio bytes in PostgreSQL.

Database constraints should reinforce unique ODL codes, valid controlled values, referential integrity, ordered team membership, and single-current-assignment behavior. Transaction boundaries must keep an ODL change and its history event consistent.

## 5. API shape

Use versioned JSON REST endpoints under `/api/v1`. Exact payloads are defined during the API-contract step. Expected resource groups are:

- session/current role;
- categories and teams;
- intake, transcription, draft interpretation and confirmation;
- work-order list/detail and allowed actions;
- assignment acceptance/refusal and fulfillment;
- reminders and history;
- operator WebSocket event stream;
- health/readiness.

Mutation commands accept an idempotency key where duplicate delivery or tapping is plausible. Errors use one stable envelope with machine code, human message, field details, and correlation ID.

WebSocket messages are post-commit notifications containing event name, ODL identifier, version, and the minimal changed representation. Clients reconnect and refetch; the socket is not the source of truth.

## 6. Provider strategy

Define narrow application ports for:

- `AIInterpreter`: text/transcript to a versioned ODL draft proposal;
- `Transcriber`: audio asset to Italian transcript;
- `ObjectStore`: put/get/delete application-owned audio objects;
- `Notifier`: technician assignment notification containing a mobile link.

The first implementation of every port is local and deterministic. This enables the full demo and automated tests without external accounts, network calls, or cloud costs. Provider selection occurs through configuration, never scattered conditionals.

## 7. Security and data handling

- Use server-side authorization for every command and query.
- Store technician action tokens only as hashes, with an expiry and one assignment scope.
- Treat phone, email, address, transcript, and audio as personal data; never log their full values by default.
- Keep secrets in environment variables locally and out of source control.
- Validate upload type and size, generate storage keys server-side, and prevent user-controlled paths.
- Escape rendered content and use parameterized database access.
- Include correlation IDs in logs; redact tokens and personal data.

Production-grade identity, retention automation, and cloud security configuration are roadmap items, not MVP behavior.

## 8. Local runtime and quality gates

The later local environment should use containers for PostgreSQL and, when helpful, an S3-compatible local object store; frontend/backend may run directly for rapid development. Seed data must create the initial categories, one routing team per useful demo category, three technicians, one team lead, and demo users.

Testing layers:

- unit tests for transitions, routing order, refusal semantics, and validation;
- integration tests for repositories, transactions, idempotency, and API authorization;
- frontend component tests for draft review and role actions;
- one end-to-end demo path, including live dashboard update;
- provider contract tests shared by fake and later real adapters.

Formatting, linting, static typing, migrations, tests, and production builds become mandatory gates as their modules are introduced.

## 9. Deferred deployment mapping

The reference architecture maps the static frontend to S3/CloudFront, the containerized FastAPI/WebSocket backend to one EC2 instance, PostgreSQL to RDS, audio to S3, transcription to Amazon Transcribe, AI to Amazon Bedrock, and messaging to Twilio WhatsApp. IAM, Secrets Manager, CloudWatch, and AWS Budgets support least privilege, secrets, basic observability, and cost control.

This is a target mapping only. No cloud resource, SDK integration, credential, or deployment automation belongs in the project until its explicit roadmap step.


## 10. Delivered WorkOrder API slice (2026-09-08)

The explicitly requested CRUD slice uses `/api/work-orders` and integer IDs from
existing SQLAlchemy models. This supersedes the `/api/v1` convention for these
endpoints. Pydantic schemas reject unknown input fields; synchronous thin routes
use the existing `get_db` session dependency and a dedicated application service
that owns SQLAlchemy queries and commits. No separate repository is necessary
for this small slice. FastAPI's standard `detail` errors are used here.

Creation sets `APERTO` and `reminders_count = 0`; database defaults generate
creation/update timestamps. Codes use `SOLVO-YYYYMMDD-XXXXXXXXXXXXXXXX`, with a
UTC date and 16 uppercase random UUID hexadecimal characters, protected by the
existing database unique constraint. Categories must exist; the current category
model has no active flag. The existing stored reminder counter cannot be set directly by API clients;
reminder creation increments it atomically.

The dedicated status endpoint uses the explicit transition map in
`app/domain/work_order_status.py`: APERTO → IN_CORSO/ANNULLATO,
IN_CORSO → EVASO/ANNULLATO, EVASO → CHIUSO/IN_CORSO; CHIUSO and ANNULLATO
are terminal. Same-status requests succeed without mutations or new history.
Invalid transitions return 409 and invalid enum inputs remain 422. The service
refreshes and locks the ODL row with `FOR UPDATE` before validating the current
status on PostgreSQL, so concurrent requests cannot use stale status values.
Status updates and their history commit together; failures explicitly roll back.
The policy has no HTTP or SQL operations and introduces no actor restrictions.

POST `/api/work-orders/{id}/reminders` requires a `created_by` integer identifying
an existing user, because the existing Reminder model has a non-null foreign key.
This is caller-supplied attribution only; no authentication is introduced.
Unknown users return 422. The service increments the counter using
`reminders_count = reminders_count + 1` in SQL, inserts the Reminder using the
server timestamp default, and appends `REMINDER_CREATED` history in one
transaction. Any database failure rolls back the counter, reminder, and history.
Each successful POST creates a new reminder; there is no status restriction.

GET `/api/work-orders/{id}/reminders` and `/history` return their respective
records ordered by creation timestamp descending, then ID descending for ties.
All three endpoints use the existing ODL dependency to return 404 for missing
ODLs. History includes creation, actual status changes (old and new values), and
reminders. Generic no-op updates do not append history.

Deletion is physical and uses existing ORM cascades, including deletion of the
ODL's history; history is otherwise append-only. Models and migrations are
unchanged. Authentication and authorization are not delivered in this slice.
SQLite API tests cover persistence, rollback on history failure, and stale ORM
objects; PostgreSQL-specific row-lock concurrency is not exercised by that suite.
