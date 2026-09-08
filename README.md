# SOLVO

SOLVO is an AI-assisted work-order and facility service desk. A requester describes a fault by text or audio, reviews an editable structured ODL (Ordine di Lavoro) draft, and confirms it. Deterministic backend rules route the confirmed ODL to technicians, while operators monitor progress in a real-time Control Center.

The backend contains a FastAPI health endpoint, SQLAlchemy models/migrations, and the WorkOrder CRUD API slice of Step 3. The complete Step 3 workflow is not delivered.

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
- Technician routing: three technicians followed by the team lead.
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
| PATCH | `/api/work-orders/{id}/status` | Set any valid ODL status, 200 |
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
atomically. Status updates have no workflow restrictions in this slice.

See `docs/ARCHITECTURE.md` section 10 for the delivered scope and decisions.
