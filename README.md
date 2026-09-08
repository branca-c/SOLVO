# SOLVO

SOLVO is an AI-assisted work-order and facility service desk. A requester describes a fault by text or audio, reviews an editable structured ODL (Ordine di Lavoro) draft, and confirms it. Deterministic backend rules route the confirmed ODL to technicians, while operators monitor progress in a real-time Control Center.

The backend contains a FastAPI health endpoint, SQLAlchemy models/migrations, and the WorkOrder CRUD, reminders, history, status-policy, and assignment-routing API slice of Step 3. The complete Step 3 workflow is not delivered.

## Source of truth

- Functional and technical reference: `docs/design/SOLVO_Guida_Tecnica_MVP_v0.1 (2).pdf`
- Visual reference: `docs/design/guida_stile_solvo_e_dashboard_ticket (1).png`
- Product scope: `docs/SPEC.md`
- Technical boundaries: `docs/ARCHITECTURE.md`
- UI tokens and dashboard rules: `docs/DESIGN_SYSTEM.md`
- Ordered delivery and future work: `docs/ROADMAP.md`
- Contributor/agent rules: `AGENTS.md`

When documents conflict, the PDF governs functional/technical intent and the PNG governs visual decisions. Explicit scope corrections captured in the foundation documents take precedence for this build.

## MVP at a glance

- Roles: requester, operator, technician.
- Priorities: `PROGRAMMABILE`, `BASSA`, `MEDIA`, `ALTA`, `URGENTE`.
- Statuses: `APERTO`, `IN_CORSO`, `EVASO`, `CHIUSO`, `ANNULLATO`.
- Technician routing: configured category technicians by escalation order, with team leaders last.
- Technician refusal: optional notes only.
- Intended stack: React + TypeScript, FastAPI + Pydantic, PostgreSQL, REST + WebSocket.
- Local deterministic providers come first; external/AWS integrations are deferred.
- No SLA or "tempo aperto" is part of the MVP.

## Backend development

Install `backend/requirements.txt` in a virtual environment and configure
`DATABASE_URL` using `.env.example`. From `backend/`, run `alembic upgrade head`
and `uvicorn app.main:app --reload`. Categories must already exist in the database.
Interactive API documentation is available at `/docs`; health remains `/health`.

Run the full backend suite from the repository root:

```sh
backend/.venv/bin/python -m pytest backend/tests -q
```

API tests use an isolated SQLite database with foreign keys enabled and override
the session dependency. They do not require PostgreSQL, but do not verify
PostgreSQL-specific behavior. No formatting, lint, or type-check tooling is
currently configured in the backend.

## WorkOrder API

| Method | Path | Result |
|---|---|---|
| POST | `/api/work-orders` | Create ODL, 201 |
| GET | `/api/work-orders` | List newest first, 200; optional `status`, `priority`, `category_id` filters combine with AND |
| GET | `/api/work-orders/{id}` | Read ODL, 200 |
| PATCH | `/api/work-orders/{id}` | Update supplied editable fields, 200 |
| PATCH | `/api/work-orders/{id}/status` | Apply an allowed status transition, 200 |
| POST | `/api/work-orders/{id}/reminders` | Create a reminder, 201 |
| GET | `/api/work-orders/{id}/reminders` | List reminders newest first, 200 |
| GET | `/api/work-orders/{id}/history` | List history newest first, 200 |
| DELETE | `/api/work-orders/{id}` | Physically delete ODL and cascading related records, 204 |

Create requires `user_first_name`, `user_last_name`, `user_phone`, `fault_address`,
`category_id`, `priority`, and `description`; `user_email` is optional. Generic
PATCH accepts only these fields. Omitted fields are preserved; only email can be
explicitly cleared with `null`. Unknown fields, invalid enums, and nonexistent
categories return 422. Missing ODLs return 404.

The server generates `SOLVO-YYYYMMDD-XXXXXXXXXXXXXXXX` codes using the UTC date
and 16 random uppercase hexadecimal characters from a UUID; the database enforces
uniqueness. Status starts at `APERTO`, the reminder counter starts at zero, and
timestamps are server-managed. Creation and actual status changes record history
atomically.

Reminder creation requires JSON `{"created_by": 1}` identifying an existing user.
The existing model requires a non-null user foreign key; this is caller-supplied
attribution, not authentication. Missing/null/unknown users return 422. The server
creates the timestamp, increments `reminders_count` in SQL, and appends a
`REMINDER_CREATED` history entry in a single transaction. A storage failure rolls
back all three changes. Each successful POST creates a separate reminder.
Reminders are accepted in any ODL status. Reminder and history lists sort by
`created_at DESC, id DESC` and return 404 for a nonexistent ODL.

Allowed status changes:

| Current | Allowed next statuses |
|---|---|
| `APERTO` | `IN_CORSO`, `ANNULLATO` |
| `IN_CORSO` | `EVASO`, `ANNULLATO` |
| `EVASO` | `CHIUSO`, `IN_CORSO` |
| `CHIUSO` | None |
| `ANNULLATO` | None |

Same-status requests return 200 without changing timestamps or adding history,
including in terminal states. Other forbidden transitions return 409; invalid
enum input returns 422. Real transitions append `STATUS_CHANGED` with the old
and new status in the same transaction. History also includes `CREATED` and
`REMINDER_CREATED`; generic no-op patches do not add events.

See `docs/ARCHITECTURE.md` section 10 for the delivered scope and decisions.


## Technician assignment API

Technicians must be configured in the database for each category. Routing uses
all configured technicians: normal technicians by `escalation_order`, then team
leaders by `escalation_order` (ID breaks ties). No fixed technician count is used.
Sequential routing advances after the current technician and excludes every
technician already attempted for the ODL, including during direct escalation.
A category/configuration change that removes the current technician from the
category makes sequential routing return 409.

| Method | Path | Result |
|---|---|---|
| POST | `/api/work-orders/{id}/assignments/start` | Start attempt 1, 201 |
| GET | `/api/work-orders/{id}/assignments/current` | Active PENDING, otherwise latest attempt, 200 |
| GET | `/api/work-orders/{id}/assignments` | Attempts in ascending attempt-number order, 200 |
| POST | `/api/assignments/{id}/accept` | Accept and move ODL to IN_CORSO, 200 |
| POST | `/api/assignments/{id}/reject` | Reject and create next PENDING attempt atomically, 200 |
| POST | `/api/assignments/{id}/no-response` | Mark NO_RESPONSE and create next PENDING atomically, 200 |
| POST | `/api/work-orders/{id}/assignments/escalate-team-leader` | Replace current PENDING with an untried leader attempt, 201 |

Responses include the assignment fields and a nested technician summary. Reject
and no-response return the updated previous attempt; use `current` to fetch its
successor. Reject accepts an omitted body, `{}`, or optional
`{"rejection_notes": "..."}`. It never requires a reason. Unknown payload fields
or malformed input return 422. Missing ODL/assignment returns 404; `current` also
returns 404 when no attempts exist, while the list returns `[]`.

`start` is only for an ODL with no assignment history. Repeated starts return 409,
including after acceptance; attempts are never reset to 1. Only the current
PENDING attempt can accept/reject/no-response; duplicate or stale actions return
409 without extra history. CHIUSO and ANNULLATO block all assignment mutations;
reads remain available. APERTO, IN_CORSO and EVASO allow assignment commands;
acceptance sets IN_CORSO, recording status history only if the status changes.
The accepted assignment itself links the technician to the ODL; no new field is
added to WorkOrder.

Every mutation commits assignments, ODL changes, and history together. When no
next technician is configured, reject/no-response return 409 and preserve the
previous PENDING assignment, notes, timestamps, and history. The operator may
correct configuration and retry. Direct escalation uses only untried team leaders
and may start at attempt 1 without an existing assignment. If none qualifies it
returns 409 without changing the current attempt; it never repeats a technician
or routes back to skipped normal technicians after the leader. Attempt numbers
increase by one. Existing ACCEPTED attempts remain historical during direct
escalation.

`sent_at` uses the database timestamp default and does not imply message delivery.
Accept/reject set `responded_at` on the server. NO_RESPONSE and ESCALATED keep it
null because no technician responded. The no-response action is manual.
History events are `ASSIGNMENT_STARTED`, `ASSIGNMENT_ACCEPTED`,
`ASSIGNMENT_REJECTED`, `ASSIGNMENT_NO_RESPONSE`, `ASSIGNMENT_ESCALATED`, and
`STATUS_CHANGED` when acceptance changes the ODL status. Each event identifies
the relevant attempt/technician; rejection notes are also retained.
