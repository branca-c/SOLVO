# SOLVO

SOLVO is an AI-assisted work-order and facility service desk. A requester describes a fault by text or audio, reviews an editable structured ODL (Ordine di Lavoro) draft, and confirms it. Deterministic backend rules route the confirmed ODL to technicians, while operators monitor progress in a real-time Control Center.

This repository is currently at **Step 0: project foundation**. It contains specifications and conventions only—no application code or AWS implementation yet.

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

## Current repository

```text
.
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
└── docs/
    ├── ARCHITECTURE.md
    ├── DESIGN_SYSTEM.md
    ├── ROADMAP.md
    ├── SPEC.md
    └── design/              # supplied PDF and PNG references
```

Application directories will be introduced only when their roadmap step begins.

## Development status

Do not install dependencies or attempt to run the application yet: there is intentionally no runtime at this stage. The next authorized step is **Step 1 — Repository and local toolchain** in `docs/ROADMAP.md`.

For later local configuration, copy `.env.example` to `.env` and replace development secrets. `.env` files are ignored by Git.
