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
- `reminders`: one row per textual follow-up with required text, server timestamp and actor.
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

WebSocket messages are post-commit invalidations containing event type, ODL identifier and UTC timestamp, without personal data or a changed-record payload. Clients reconnect and refetch; the socket is not the source of truth.

## 6. Provider strategy

Define narrow application ports for:

- `AIInterpreter`: text/transcript to a versioned ODL draft proposal;
- `Transcriber`: audio asset to Italian transcript;
- `ObjectStore`: put/get/delete application-owned audio objects;
- `NotificationProvider`: technician assignment notification containing a mobile link.

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

AWS deployment remains deferred in `docs/ROADMAP.md`; no AWS resources are implemented.
The delivered MVP uses one FastAPI backend with in-memory WebSocket realtime,
PostgreSQL, and Telegram Bot API or a deterministic mock for notifications.
Cloudflare Quick Tunnel is temporary development/demo access to Vite only, not a
production architecture component. The PDF's notification mapping is superseded by
this explicit decision and requires manual regeneration.


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


## 11. Delivered assignment routing slice

Assignment endpoints are registered through the existing API router. Thin routes
map service resource errors to 404 and routing conflicts to 409; Pydantic handles
422 and response serialization with a technician summary. A dedicated service in
`app/services/assignments.py` orchestrates the existing SQLAlchemy models. The
selection policy in `app/domain/assignment_routing.py` operates on technician
attributes without HTTP or database operations. Models and migrations are unchanged.

All assignment mutations lock the parent WorkOrder row (`SELECT FOR UPDATE` on
PostgreSQL) before reading current attempts, deciding eligibility, or allocating
an attempt number. Assignment records are refreshed after acquiring that lock,
so stale sessions cannot accept/reject an already completed attempt. This shares
the parent-row lock with the existing status-change service. The service commits
once and explicitly rolls back errors. The existing unique constraint on
`(work_order_id, attempt_number)` remains a database backstop; one PENDING attempt
and no repeated technician are enforced through the serialized service flow.
Direct database writes must not bypass these application invariants.

Normal technicians precede team leaders, each group ordered by escalation_order
and ID. Selection uses the ODL's current database category and never hardcodes a
team size. Next-candidate selection moves forward from the current technician
and excludes all previously attempted IDs. If the current technician no longer
belongs to the category, sequential routing conflicts rather than silently
restarting the chain. Direct escalation selects the first untried team leader.
Multiple configured leaders are deterministic; no eligible leader returns 409.

Start creates attempt 1 only when there are no attempts; any later start returns
409. Reject/no-response validate the next candidate before changing the prior
attempt. Exhaustion returns 409 with the entire prior state unchanged, including
PENDING and history. Success returns the completed previous assignment, and
`current` exposes the new PENDING attempt. Escalation marks the active PENDING
attempt ESCALATED, if present, and creates a new leader attempt numbered
`max(attempt_number) + 1` (or 1 with no history). Accepted attempts are historical
and are not modified by escalation. A technician is never attempted twice.

All mutations reject terminal ODLs; queries remain available. Acceptance sets
IN_CORSO using the existing status policy and writes status history only for a
real change. The accepted Assignment represents the assigned technician; no new
WorkOrder column is needed. Start, accept, reject, no-response, and escalation
append history in their mutation transaction. Database defaults set sent_at;
server UTC time sets responded_at for accept/reject. NO_RESPONSE and ESCALATED
leave responded_at null. No sent_at/history event represents a delivered message.

API tests cover routing, duplicate/stale actions, terminal restrictions, history,
and rollback after a simulated history failure. They use SQLite; PostgreSQL's
concurrent row-lock behavior is not exercised by this suite. This slice adds no
transport, authentication, scheduler, availability, zone, or SLA logic.

## 12. Delivered first frontend slice

The React/TypeScript Vite app lives in `frontend/`. Components, four pages,
a small fetch service, shared API types/helpers, and a cancellable resource hook
keep the implementation local and explicit. Hash-based navigation supports
refresh, links, and browser back/forward without a routing dependency or server
fallback configuration. WorkOrder data has no global cache or client-side data store:
page entry and the refresh action fetch current data; create navigates to detail;
successful status changes refetch the ODL and related activity.

The browser requests same-origin `/api` paths. Vite dev and preview proxy them to
`VITE_API_BASE_URL`, loaded from `frontend/.env`, defaulting to
`http://127.0.0.1:8000`. This connects to existing FastAPI without backend CORS
changes. The environment value configures the local proxy, not a production
URL embedded in the JavaScript. A standalone static build requires an external
same-origin `/api` proxy; deployment is not implemented. No backend routes,
schemas, models, settings, or dependencies were changed for this frontend.

Dashboard derives five summary counts from the complete WorkOrder list and shows
the latest eight. The ODL list sends status/priority filters to FastAPI. Category names now use the reference-data lookup described in section 16;
creation uses a select and retains category IDs in API payloads. The detail retrieves ODL, reminders,
history, and assignments; related sections have independent errors/retry states.
Status options mirror the explicit backend map, while FastAPI validates each
PATCH. HTTP errors appear inline; failed creation preserves entered form values.
No mutation is retried automatically. Generic fetch errors, FastAPI detail
strings and validation arrays are handled centrally. Navigation/filter changes
abort stale read requests.

The UI uses the binding Fresh palette, Poppins bundled as local font assets,
indigo sidebar, aqua actions, white surfaces, compact data tables and text badges.
Five summary cards follow the explicit frontend task rather than the four-card
reference composition. Small screens use stacked table rows, keyboard users can
open each ODL by its link, forms have labels, and feedback uses live regions.
Tecnici has editable contacts and read-only routing fields; settings remains disabled. Vitest and Testing Library cover
key page flows and helpers; `tsc --noEmit` and `vite build` are quality gates.


## 13. Delivered AI-assisted text draft slice

`POST /api/ai/work-order-draft` accepts only text (trimmed, 1–10000 characters).
The thin route obtains the SQLAlchemy dependency and selected provider, then
calls `work_order_drafts.build_draft`. The provider protocol receives text and configured category names only:
it has no database session, repository, workflow commands, or creation method.
Its return value is untrusted and validated against `ExtractedWorkOrder`, which
forbids extra fields, workflow fields and provider-supplied database IDs. The
response uses `WorkOrderDraft` with an editable description (empty when missing) and warnings.
Names, phone, email and address absent from the source are discarded even if a
provider proposes them. Category names resolve by case/whitespace-normalized
exact matching against configured Category rows; missing or ambiguous matches
return null IDs and warnings. The service only SELECTs categories: there is no
commit, persistence side effect, or WorkOrder creation dependency.

`AI_PROVIDER=mock` selects deterministic keyword/explicit-field extraction;
`fake` remains a compatibility alias for the previous environment example.
`ollama` selects the local HTTP adapter described below. Other values produce a
recoverable 503. No AWS client, credentials, cloud inference,
agent or tool-calling mechanism is introduced. The interface is the extension
point for the Bedrock target recorded in Roadmap Step 8; it is not implemented.
Invalid provider output returns 502 and provider failures return sanitized 503
messages. Tests override the provider dependency to verify validation and failure
handling, and inspect SQL to verify the absence of writes.

The existing create page now has manual and assisted modes sharing one editable
form and the original creation service. Analysis and creation are separate forms
and separate requests. Missing draft values remain empty (including priority),
so browser and backend creation validation still require completion. Warnings
and proposed category name are shown beside the review form. Only explicit
confirmation calls `POST /api/work-orders`; no new creation endpoint exists.
Mode switching preserves edits, reanalysis explicitly replaces the form values,
and leaving the page aborts pending analysis. Neither source text nor drafts are
stored in browser persistent storage. This delivery covers text only.

### Audio intake slice

The transcription port accepts temporary audio bytes and MIME type and returns text;
it has no database access. The audio orchestration service validates bounded input,
invokes transcription and reuses `build_draft` without database mutations. FastAPI
closes its spooled upload in a finally block on success and failure. No audio asset
row, permanent file, queue, or object storage is created. Multipart parsing may spool
the incoming upload before application size validation; the service reads at most
its configured limit plus one byte. MIME validation is not codec validation in mock mode.
Deterministic mock and real local faster-whisper adapters are delivered. Unsupported provider configuration
fails explicitly (503); it never silently switches providers.
The React audio component releases microphone tracks on stop/error/unmount and aborts
pending analysis on unmount. JSON and multipart requests share the API client;
multipart Content-Type is left to the browser. All intake modes share one editable form.

## 14. Signed technician actions and explicit messaging

No model/migration change is required. The standard-library HMAC-SHA256 token signs
`v1.assignment_id.expiry` with a purpose prefix and a separate environment secret.
Validation enforces canonical syntax, a constant-time signature comparison and
expiry before database lookup. The token is signed, not encrypted; it contains no
personal data or secret. A shared strong secret persists across restarts/workers;
rotation revokes all links. There is no per-token revocation table. Existing
assignment state checks prevent repeated or superseded mutations.

Public routes serialize a dedicated allowlist schema and call the original
assignment service for accept/reject. The helper builds URLs using the configured
frontend base. Public data and link responses are no-store; the frontend sets
no-referrer. Do not include bearer links in audit descriptions or application logs;
access logs at the server/proxy must redact token paths. Operator APIs have no login
in this delivery and must remain on a trusted network; token validation protects
the public endpoints only.

`services/notifications.py` defines NotificationProvider.send(technician_id, message)
and immutable Delivery metadata. MockNotificationProvider returns a deterministic
hash-based ID without constructing an HTTP client. TelegramNotificationProvider
uses the existing HTTPX dependency to POST HTTPS JSON to the fixed Telegram Bot API
host, with a 10-second timeout, plain text and disabled link previews. The bot token
is a server-only SecretStr. HTTP request URL logging redacts bot credentials;
provider errors omit raw responses, URLs and exception chains. Responses require
`ok=true` and a positive integer message_id before recording submission success.
`NOTIFICATION_PROVIDER=mock|telegram` selects the provider without routing changes.
Unknown providers and incomplete/invalid configuration fail closed with 503.

Demo destination resolution belongs to the Telegram adapter: TELEGRAM_DEMO_CHAT_ID
is used for every technician ID. No phone-to-chat conversion, model field or migration
is introduced. The signed link still identifies the actual routed assignment.
Production identity and reliable delivery work belong only in ROADMAP. No SDK,
scheduler, background job, Telegram webhook or inline callback is introduced.

For phone demos the Quick Tunnel URL becomes TECHNICIAN_ACTION_BASE_URL and its
exact hostname is explicitly allowed by Vite using its additional-host environment
setting. Vite proxies REST and WebSocket to the same backend. The tunnel and operator
APIs are unauthenticated, so this temporary exposure is limited to fictional demo
data and stopped afterwards. README contains the manual flow; no installation or
setup script, wildcard host allowance or temporary URL is committed.

Notification orchestration reuses the parent-row lock/current-PENDING check so
assignment transitions cannot race an active submission on PostgreSQL. Successful
provider acceptance/simulation and its history commit together locally. Sending to
an external service cannot be rolled back with the database: timeout or commit
failure may have uncertain external delivery. No automatic retries are attempted;
explicit repeat notify requests can send again. Exactly-once external delivery is
not claimed. The UI distinguishes simulation/submission from confirmed delivery.

The existing hash navigation remains for operators. A pathname technician route is
recognized before that navigation and renders the mobile page without Layout.
SPA fallback must serve that path. Both public actions share the API client and
return the same limited assignment projection. Realtime is delivered by the following single-instance slice.

## 15. Single-instance realtime implementation

The in-memory ConnectionManager owns connected sockets and serializes writes per
client on the ASGI event loop. Synchronous service threads submit broadcasts through
asyncio.run_coroutine_threadsafe; no database session or ORM instance crosses that
boundary. Sends run concurrently across clients with a two-second bound per send
(including lock wait). Failed clients are removed and closed best-effort.
WebSocket input is ignored; it cannot trigger workflow changes or relay messages.

Services publish scalar event metadata after commit and before response refresh.
The assignment transaction helper collects event tuples and drains them only after
commit succeeds, outside its rollback handler. Public technician routes still use
those services. The publisher catches scheduling/send failures and logs no payloads;
committed business data is never reverted because of WebSocket failure. The existing
delete operation emits a deletion invalidation so Dashboard/detail do not stay stale.
This is not an outbox: a process failure can lose events and delivery order across
concurrent transactions is not guaranteed. Re-fetching is authoritative.

Each active Dashboard/detail page has one socket with cleanup on unmount. The
frontend derives ws/wss from its origin and Vite proxies upgrades to the existing
configured backend. The client ignores unknown/malformed messages, uses bounded
reconnect backoff and refetches after every connection. A hook coalesces events and
filters detail IDs; no client-side event store exists. Activity refresh preserves
mounted controls and previous data while replacing fetched results.

Run only one backend worker/instance. Connection memory is process-local and has no
shared pub/sub, persistence or replay. The endpoint shares the trusted-network scope
of existing unauthenticated operator APIs. Further scaling requirements are recorded
only in ROADMAP.

## 16. Reference data and explicit demo bootstrap

Two read-only routes reuse existing SQLAlchemy models and the session dependency.
Technicians join Category for category_name, avoiding per-row lazy queries, and
sort in routing order within each category. No model or migration changes.
The seed is an explicit Python module, not an app startup hook. Exact category
names and deterministic demo emails identify rows; an existing conflicting
routing slot aborts the transaction without overwriting configuration. The user
email is an application-level seed key (the model has no email unique constraint),
so the local command is intended for sequential, not concurrent, invocation.
All inserts commit together, with rollback on any failure. It creates no ODLs.

A shared in-memory promise caches successful category reads for a browser session
and deduplicates concurrent loads. Failed requests evict the cache for retry;
unmounted consumers ignore results through the resource hook. A full browser
reload picks up external reference changes. The same name lookup is used by
ODL tables/detail/assignments, and all intake modes use one select. Draft resolution prefers
an existing ID, otherwise one normalized exact name match, including when the
category request completes after analysis. API creation still validates category
existence. No new dependencies, settings, providers or workflow mutations.

## 17. Operator detail actions

Frontend API methods wrap the existing assignment start/no-response/escalation
and reminder POSTs. ActivityPanels receives ODL status and the detail refresh
callback. Successful mutations invalidate local resource reads immediately;
errors also refetch authoritative state without retrying the write. The existing
WebSocket hook and backend are unchanged. Buttons are disabled during mutations
and assignment refresh, and terminal status hides assignment mutation controls.
Start is offered only for an empty chain because the existing endpoint rejects
all repeat starts, including after acceptance. No routing policy is reimplemented.
VITE_DEMO_USER_ID is an explicit positive safe integer with no default, sent as
created_by for demo reminders only. It provides attribution, not authentication,
and does not create or validate the database user locally.


## Operator management slice

Dashboard, ODL list and detail expose Dettaglio, Modifica ODL and Elimina.
Editing reuses PATCH /api/work-orders/{id} for requester names, phone/email,
fault address, category, priority and description. Status uses its existing
workflow; code, IDs, timestamps and reminder counter are not editable.
Deletion reuses DELETE, requires confirmation showing the ODL code, refreshes
current data and returns from detail to the ODL list. Physical deletion with
cascading dependent notes/history is the current MVP behavior.

WorkOrderNote stores id, work_order_id, text, server timestamp created_at and
nullable created_by (null in the no-auth MVP). Alembic revision 20260916_0002
adds work_order_notes and the cascading WorkOrder relationship.
POST /api/work-orders/{id}/notes accepts only nonempty trimmed text; note and
NOTE_ADDED history commit atomically and roll back together on storage failure.
GET /api/work-orders/{id}/notes orders created_at DESC, id DESC. Both return 404
for missing ODLs. Description is preserved. Detail offers Note, Aggiungi nota
and dated entries. Post-commit work_order.updated reuses existing realtime
invalidation so open detail and history refresh.

Dashboard/list show reminder counts and a quick Sollecito action using the
existing POST and VITE_DEMO_USER_ID attribution (a positive safe integer with
no default, not authentication). Missing/invalid configuration disables the
action with an explanation. Successful writes refresh counts immediately;
existing reminder history and WebSocket behavior remain. The ODL list now also
subscribes to the existing realtime hook.

PATCH /api/technicians/{technician_id} accepts only first_name, last_name, phone
and nullable email. Blank required names/phone, null required fields, and extra
fields return 422; missing technician returns 404. Tecnici provides contact
editing and feedback with immediate refresh. Category, escalation order and
team-leader role remain read-only configuration; routing rules are unchanged.
**Technician phone is editable real contact data, but the CURRENT Telegram demo
transport uses TELEGRAM_DEMO_CHAT_ID, not the technician phone number.**
No authentication, provider changes or new notification channels are included.


## Textual solleciti and notes presentation

A sollecito is a timestamped textual follow-up/request, not merely a counter.
The existing reminder POST now requires `created_by` and `text`; Pydantic trims
outer whitespace, rejects missing/empty/whitespace-only text and enforces a
2000-character maximum. GET returns the text with the original reminder fields,
ordered created_at DESC, id DESC. User verification and missing-ODL 404 remain.
Reminder insertion, atomic SQL counter increment and REMINDER_CREATED history
still commit together and roll back together. History records the reminder ID
and creator concisely without duplicating the message. The existing post-commit
reminder.created WebSocket event remains unchanged.

Alembic revision `20260916_0003` (after `20260916_0002`) adds a nullable text
column, fills existing rows with **Sollecito precedente: testo non disponibile.**,
then enforces NOT NULL with no default for new rows. This neutral legacy label
indicates missing historical content and does not invent a reason. Existing IDs,
creator, timestamps and counters are preserved. Downgrade removes the text column
and its content while preserving reminder rows. Run `alembic upgrade head` before
starting the updated application; previous migration files are unchanged.

Dashboard/list Sollecito and detail Aggiungi sollecito share one compact dialog:
Aggiungi sollecito, Motivo / informazioni del sollecito textarea, Annulla and
Aggiungi sollecito. Opening/cancelling never creates a reminder. Explicit submission
sends the reviewed text with VITE_DEMO_USER_ID; success closes the dialog, displays
inline confirmation and immediately refetches counts/data/history. Errors preserve
the message for correction. Missing/invalid demo identity disables creation.
Detail displays text prominently, creator ID and date/time, newest first.

The Note section now shows existing notes first, or Nessuna nota presente,
followed by spacing/separator, Aggiungi nota heading, textarea and button.
This changes presentation only; WorkOrderNote backend behavior is unchanged.
PDF regeneration remains deferred.


## Local speech recognition adapter

LocalWhisperTranscriptionProvider implements the existing audio-bytes transcription
port without database access. Lazy imports isolate optional runtime initialization
from mock use. The provider factory caches local adapters by model/device/compute/
language (bounded to four configurations); each owns a lazy model and a lock serializing
first load and inference. Factory construction is also locked to avoid duplicate
adapters on concurrent first requests. One stable application configuration reuses
one model per backend process. Restart releases that cache; workers each own a model.

PyAV decode_audio receives BytesIO of the actual upload and resamples to 16 kHz.
The stream closes even on decoder failure; the adapter writes no temporary file.
FastAPI’s existing multipart spool remains closed by the route. Segment generators
are consumed inside the model lock; nonblank segments are joined with spaces and
trimmed. VAD filters nonspeech. No recognized text produces a readable 422.

Auto device selection probes CTranslate2 CUDA availability defensively. GPU model
initialization or deferred inference failure retries with CPU/int8 and retains the
CPU model for later requests. Explicit CPU/CUDA remains configurable. Failed model
initialization is not cached as a successful model and can be retried. Dependency,
model and runtime failures expose fixed messages (503), without raw exception data.
Unreadable audio is 422. No CUDA path or external transcription API is hardcoded.
The first model load can download/cache weights using faster-whisper; provisioned
local model directories support fully offline initialization.

Audio orchestration still reuses build_draft and category resolution with no writes.
Additive nullable transcription_source metadata distinguishes mock/local_whisper;
the browser keeps MediaRecorder unchanged and displays the corresponding source.
Tests replace faster-whisper/CTranslate2 modules with stubs and never download models.
The sole new direct dependency is faster-whisper (including its decoding/inference
runtime dependencies). Amazon Transcribe remains unimplemented; PDF is unchanged.


## Local Ollama extraction adapter

AIProvider.extract(text, categories) receives only source text and names from the
current Category query. build_draft uses the same rows for normalized exact name
resolution; the provider never receives a database session or category IDs.
Both text and audio orchestration call build_draft. Whisper is speech recognition,
Ollama is semantic extraction/summarization; neither creates WorkOrders.

AI_PROVIDER=mock retains deterministic network-free test/demo behavior (fake alias).
AI_PROVIDER=ollama uses OllamaAIProvider with existing HTTPX, synchronous `/api/chat`,
stream=false, temperature=0 and ExtractedWorkOrder.model_json_schema() as format.
Category choices are constrained to supplied names (only null for an empty list).
Pydantic validates message.content as ExtractedWorkOrder before the application
validates it again. Extra fields, IDs, workflow commands and invalid priorities
are forbidden by the existing schema; no duplicate extraction schema is introduced.

OLLAMA_BASE_URL defaults to http://127.0.0.1:11434; OLLAMA_MODEL has no default model
and is required for ollama; OLLAMA_TIMEOUT_SECONDS defaults to 60 and must be positive
and finite. Configuration is validated at provider construction so manual intake
and mock remain usable with no Ollama model. No model pull, SDK, retries or silent
provider substitution. HTTP proxy environment settings are ignored for the local adapter.
Missing model configuration, connectivity, 404 model availability, timeout and other
HTTP failures map to sanitized 503; malformed envelope/JSON/Pydantic output maps to
502 on both endpoints. Raw model responses and exception details are not returned.

A focused Italian system prompt treats user text as data, requests null for missing
or uncertain fields, gives priority semantics and requires technical summaries only.
An exact-value boundary check rejects Ollama summaries repeating extracted names,
phone, email or address; it does not rewrite language and cannot detect every
paraphrase. Existing source grounding excludes invented contact/address proposals,
allowing punctuation/spacing normalization. Missing description becomes an empty
form field with a warning rather than a copied transcript. Creation schemas still
require a nonempty description. Mock keeps its source-text description for compatibility.

HTTP MockTransport tests exercise parsing, provider selection/configuration, errors,
field mapping, categories, priorities and equal text/audio requests; SQL observation
verifies SELECT-only analysis. Human editing and explicit confirmation use the
unchanged creation endpoint. Amazon Bedrock is a future optional cloud adapter
(ROADMAP Step 8). No AWS, transcription, Telegram, authentication or migration changes
are part of this adapter; existing local Whisper work is preserved. PDF is unchanged.


## Hybrid draft classification

Ollama remains the primary semantic extractor. After ExtractedWorkOrder validation
and normal category resolution, build_draft fills only missing/unresolved category
and missing priority using conservative deterministic rules on the original request
or transcript. Valid AI proposals are never overwritten. Provider errors and invalid
output still fail explicitly; this is not a switch to the mock provider. The same
post-validation rules can fill unresolved fields from other valid provider contracts.

The pure domain classifier in `backend/app/domain/draft_classification.py` proposes
category names, never IDs. Case folding, whitespace/punctuation normalization and
explicit Italian singular/plural lexical variants cover Ascensore, Idraulico,
Climatizzazione, Riscaldamento, Elettrico, Rete, Vetri, Serramenti, Edile, Antincendio,
Sicurezza and Arredi. Exactly one supported category is required, considering
competing signals even when a competing category is not configured. The proposal
must match exactly one normalized configured database category; its canonical name
and ID are returned. No unmatched request defaults to Altro.

Priority fallback runs only for a missing/null validated AI priority and uses the
original report, never the generated description. Valid AI priorities are preserved.
Rules evaluate URGENTE → ALTA → MEDIA → BASSA → PROGRAMMABILE. URGENTE requires
explicit danger: trapped people, fire/smoke, gas leak/strong gas odor, exposed wires,
sparks/electrical risk, grave flooding or water with explicit immediate damage.
The word “urgente” alone is insufficient. ALTA requires a blocked/nonrestarting
elevator, an explicitly complete important-service outage (including a whole
building without heating), or a fault explicitly preventing normal use. An ordinary
“riscaldamento non funzionante” is MEDIA, not evidence of a complete outage.
MEDIA covers concrete active malfunctions/leaks without stronger severity evidence.
BASSA covers explicit minor/cosmetic defects or minor deterioration/non-critical
components with continued usability. PROGRAMMABILE covers preventive/planned work
without evidence of active failure. An independent active failure takes precedence
over minor/planned wording. Insufficient evidence leaves priority null.
Recognizable requester-name, phone, email and address spans are excluded from
priority evidence; they do not alter the extracted contact or address fields.

Paired quoted passages and recognizable example clauses are excluded. Simple
clause-local negation checks suppress obvious negated signals, including negated
danger/leaks and coordinated negations; this is conservative
lexical matching, not comprehensive language understanding. Ambiguity, unavailable
categories and insufficient evidence retain manual-selection warnings. Existing
warnings identify values supplied by deterministic rules without adding provenance
fields or database storage. Description handling remains unchanged: the LLM technical
summary is primary and missing summaries stay empty. Human review and explicit
confirmation remain mandatory; analysis only reads the database and creates no ODL.
No frontend, schema, migration, Whisper, Telegram or AWS changes are required.
The technical PDF is not regenerated.
