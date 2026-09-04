# AGENTS.md

## Mission

Build SOLVO incrementally as a simple, reliable, demonstrable MVP for facility-maintenance work orders (ODL). The functional and technical source of truth is `docs/design/SOLVO_Guida_Tecnica_MVP_v0.1 (2).pdf`; the visual source of truth is `docs/design/guida_stile_solvo_e_dashboard_ticket (1).png`.

Before implementing a step, read `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN_SYSTEM.md`, and the relevant section of `docs/ROADMAP.md`.

## Scope rules

- Work one roadmap step at a time. Do not anticipate later steps.
- Keep the MVP small, end-to-end demonstrable, and deterministic outside AI interpretation.
- Do not implement application code until a later task explicitly requests it.
- Do not implement AWS resources or deployment yet.
- Do not add SLA concepts, SLA timers, deadlines derived from SLA, or a "tempo aperto" field/metric.
- Put proposed or out-of-scope features only in `docs/ROADMAP.md`; do not leak them into the MVP specification.
- Preserve the exact enum values:
  - priorities: `PROGRAMMABILE`, `BASSA`, `MEDIA`, `ALTA`, `URGENTE`
  - ODL statuses: `APERTO`, `IN_CORSO`, `EVASO`, `CHIUSO`, `ANNULLATO`
- A technician refusal accepts only optional notes. Never require a reason or introduce a refusal-reason enum.
- Categories are data, not a code enum.

## Engineering conventions

- Intended stack: React + TypeScript frontend, Python + FastAPI + Pydantic backend, PostgreSQL database.
- Keep domain rules independent from HTTP, persistence, AI, messaging, and cloud providers.
- AI may propose structured ODL data but may not write directly to the database or decide workflow transitions.
- Validate all AI output and require user review/confirmation before ODL creation.
- Make repeated webhook/action handling idempotent and state transitions explicit.
- Record meaningful ODL, assignment, reminder, acceptance/refusal, fulfillment, closure, and cancellation events in an append-only history.
- Keep secrets out of the repository. Update `.env.example` whenever configuration changes.
- Add tests with each implementation step, prioritizing domain transitions, routing, retry, reminders, and duplicate actions.

## UI conventions

- Treat `docs/DESIGN_SYSTEM.md` as binding.
- Reproduce the reference dashboard’s bright SaaS composition: indigo gradient sidebar, white cards, subtle cool borders/shadows, compact data table, rounded badges, and aqua primary actions.
- Use the exact palette and priority colors. Do not substitute framework defaults.
- Use Italian product copy and the ODL vocabulary in the specification.
- Build responsive views: desktop-first Control Center and touch-friendly technician/requester flows.

## Change discipline

- Keep documentation consistent with delivered behavior.
- Do not silently change product rules. Record material architectural decisions in `docs/ARCHITECTURE.md`.
- Do not commit generated files, dependencies, local databases, secrets, audio uploads, coverage, or build output.
- Before handing off a step, run the relevant formatting, lint, type, and test checks and report any check that could not run.

