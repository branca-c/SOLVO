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
- Local deterministic providers come first; Telegram Bot API is available for demo notifications; AWS integrations are deferred.
- No SLA or "tempo aperto" is part of the MVP.

## Backend development

Install `backend/requirements.txt` in a virtual environment and configure
`DATABASE_URL` using `.env.example`. From `backend/`, run `alembic upgrade head`
then the explicit demo seed below and `uvicorn app.main:app --reload`.
Interactive API documentation is available at `/docs`; health remains `/health`.

Run the full backend suite from the repository root:

```sh
backend/.venv/bin/python -m pytest backend/tests -q
```

API tests use an isolated SQLite database with foreign keys enabled and override
the session dependency. They do not require PostgreSQL, but do not verify
PostgreSQL-specific behavior. No formatting, lint, or type-check tooling is
currently configured in the backend.

## Local first-run and demo reference data

Prerequisites: install backend requirements in `backend/.venv`, install frontend
packages with `npm ci`, and configure local `.env` from `.env.example` (including
`DATABASE_URL`). With the backend virtual environment activated:

1. Start PostgreSQL and ensure the configured database exists.
2. From `backend/`, run `alembic upgrade head`.
3. From `backend/`, run the explicit seed command:

   ```sh
   python -m app.scripts.seed_demo
   ```

4. From `backend/`, start `uvicorn app.main:app --reload`.
5. In another terminal, from `frontend/`, start `npm run dev` and open
   `http://127.0.0.1:5173`.

The seed inserts **local/demo data only**. It never runs at application startup
and is not automatically inserted in production. **WorkOrders are intentionally
not seeded**: create them through Nuovo ODL, manually or from a reviewed text/audio
draft. The command targets the database in `DATABASE_URL`.

Seeded categories: Vetri, Climatizzazione, Riscaldamento, Ascensore, Rete,
Elettrico, Edile, Idraulico, Serramenti, Antincendio, Sicurezza, Arredi, Altro.
Each category gets four distinct fictional people (`Demo 1` through `Demo 4`,
category as surname): three normal technicians at orders 1–3 and one caposquadra
at order 4, for 52 technicians total. Emails use `solvo-demo.example`; phone
numbers use the fictional +1 202 555 01xx range and are for mock demonstrations.
The reminder user is `Richiedente Demo`, role `UTENTE`, email
`richiedente@solvo-demo.example`. The command prints its real `created_by` ID
for the existing reminder API; it does not assume ID 1.

Repeated sequential runs reuse categories by exact name, demo technicians by
stable email, and the demo user by email. Existing rows are not overwritten.
A conflicting escalation slot or changed demo routing configuration aborts and
rolls back the whole seed. Run the command once at a time; concurrent seed runs
are not supported. No schema or migration change is required.

Read-only reference endpoints:

- `GET /api/categories`: `id`, `name`, nullable `description`, ordered by name.
- `GET /api/technicians`: `id`, `first_name`, `last_name`, `phone`, nullable
  `email`, `category_id`, `category_name`, `escalation_order`, `is_team_leader`.
  Optional positive `category_id` filters the results; an unknown category gives
  `[]`. Ordering is category name, normal technicians before leaders, escalation
  order, then ID.

The category lookup is cached in memory for the browser session; reload the page
after changing reference data externally. Loading/error/empty states prevent
creation without a configured category, and failed loads can be retried.
AI drafts select a configured category by ID, or by an unambiguous normalized
name if the ID is unavailable; unresolved categories require manual selection.

Operator assignment and reminder controls are now available in ODL detail, as
described below. They reuse the existing APIs.

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

## Frontend locale

Il primo frontend SOLVO usa React, TypeScript e Vite. Richiede Node.js 22.12+
(o una versione compatibile successiva). Avvia FastAPI sulla porta 8000 seguendo
le istruzioni backend sopra, con migrazioni applicate e categorie già configurate.
Poi, in un secondo terminale:

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Apri `http://127.0.0.1:5173`. In `frontend/.env`, `VITE_API_BASE_URL` è l’origine
FastAPI, senza `/api` finale; il default è `http://127.0.0.1:8000`. Riavvia Vite
quando cambi la configurazione. Il browser chiama `/api` sulla stessa origine e
il proxy Vite inoltra le richieste a FastAPI: non sono necessarie modifiche CORS
al backend. Le variabili frontend non devono contenere segreti.

Le pagine disponibili sono Dashboard (`#/`), ODL (`#/odl`), creazione
(`#/odl/nuovo`), dettaglio (`#/odl/{id}`) e Tecnici (`#/tecnici`). Impostazioni
rimane un placeholder disabilitato. Dashboard e lista caricano dati reali da FastAPI;
la Dashboard mostra cinque conteggi e gli otto ODL più recenti. Il conteggio
Urgenti comprende tutti gli stati; Evasi/Chiusi somma EVASO e CHIUSO.

La lista filtra per stato e priorità sul server. Dashboard, lista e dettaglio
mostrano i nomi categoria tramite un lookup condiviso. Il form manuale/AI/audio
carica un select da `/api/categories` e invia il relativo `category_id`.
La pagina Tecnici mostra categoria, ordine escalation, ruolo e telefono senza CRUD. Il dettaglio mostra ODL, solleciti,
history e assegnazioni, con errori e ricaricamento indipendenti delle sezioni.
Il form crea un ODL e apre il suo dettaglio con conferma inline. Le azioni di
stato propongono solo le transizioni consentite; il backend resta autorevole e
le modifiche riuscite ricaricano ODL e history. Il dettaglio espone anche i
controlli di assegnazione e sollecito descritti sotto.

Verifiche frontend:

```sh
cd frontend
npm run typecheck
npm test
npm run build
npm run preview
```

La preview è disponibile su `http://127.0.0.1:4173` e usa lo stesso proxy locale.
La build statica è in `frontend/dist` (ignorata da Git). Il proxy appartiene ai
server Vite di sviluppo/preview: per servire i file statici occorre inoltrare
`/api` a FastAPI sulla stessa origine. Non è stata introdotta una configurazione
di deployment. I test Vitest verificano componenti, form, transizioni, conteggi,
filtri e contratti del client usando risposte controllate; nessun dato fittizio
è incluso nel runtime dell’applicazione. Poppins è distribuito localmente nel
bundle; non vengono caricati font da servizi esterni.


## Inserimento testo assistito da AI

In **Nuovo ODL**, scegli **Assistito da AI**, incolla la descrizione e premi
**Analizza con AI**. La risposta compila il normale form modificabile. Rivedi i
dati, completa i campi vuoti, modifica categoria/priorità se necessario e premi
**Conferma e crea ODL**. Solo quest'ultimo passaggio chiama `POST /api/work-orders`.
L'inserimento manuale rimane disponibile e non chiama il servizio AI.

`POST /api/ai/work-order-draft` accetta `{"text": "..."}` (1–10000 caratteri,
esclusi testi vuoti o composti solo da spazi) e restituisce una bozza, con valori
null quando un dato manca, descrizione e avvisi. Non crea o modifica ODL, history,
assegnazioni o categorie e non conserva il testo nel database.

Configurazione backend in `.env`:

```dotenv
AI_PROVIDER=mock
```

`mock` è il default: applica regole locali deterministiche, senza servizi esterni,
credenziali AWS o dipendenze aggiuntive. Il vecchio valore `fake` è un alias.
Altri provider, compreso `bedrock`, restituiscono attualmente 503; non viene
attivato un servizio remoto né nascosto un errore tramite fallback automatico.
Il provider Bedrock con un modello Claude di classe Haiku è descritto come lavoro
futuro in `docs/ROADMAP.md`, non implementato in questa slice.

Esempio utile per il mock:

```text
Mi chiamo Ada Rossi. Telefono: +39 333 1234567;
Email: ada@example.com; Indirizzo: Via Roma 12, Milano;
C'è una perdita dal tubo del bagno.
```

Sono supportati anche campi espliciti `Nome: ...; Cognome: ...`, un indirizzo
stradale con numero civico e i principali termini di guasto indicati nella
specifica. Il mock non è un modello linguistico e non interpreta ogni variante
del linguaggio: nomi complessi possono richiedere i campi etichettati o la revisione
manuale. Più categorie candidate restano da scegliere. La categoria proposta è
risolta per nome contro le righe configurate, senza ID fissi; nomi assenti o
ambigui producono ID null e un avviso. Priorità e dati sono validati con Pydantic.
I contatti/nomi/indirizzi non rintracciabili nel testo vengono esclusi dalla bozza.

La priorità è proposta conservativamente: pericolo esplicito/immediato → URGENTE,
blocco grave → ALTA, guasto ordinario → MEDIA, piccolo inconveniente → BASSA,
manutenzione programmata/non urgente → PROGRAMMABILE. Senza indizi rimane null;
semplici negazioni come “non urgente” e “nessun pericolo” sono riconosciute. La
descrizione del mock conserva il testo originale. Non vengono inferiti stati ODL.

Errori: input invalido 422, output del provider non conforme 502, provider non
disponibile 503. Il frontend conserva il testo e permette di riprovare o passare
al manuale; non ritenta automaticamente né crea ODL in caso di errore.

### Audio-assisted intake (local mock)

Install updated backend dependencies with `backend/.venv/bin/python -m pip install -r backend/requirements.txt`.
Set `TRANSCRIPTION_PROVIDER=mock` (legacy `fake` also accepted),
`TRANSCRIPTION_MOCK_TEXT="Perdita di acqua dal tubo del bagno."` and
`MAX_AUDIO_UPLOAD_MB=10` in `.env`. The configurable server limit is 1–25 MiB;
the browser conservatively allows at most 10 MiB. No AWS credentials are required.
Every accepted file returns the configured demonstration text, **not recognized speech**.
The transcript feeds the existing AI draft pipeline (`AI_PROVIDER=mock` locally).

Under **Nuovo ODL → Assistito da AI**, upload WebM/WAV/MP3/MP4 or choose
**Registra audio → Ferma registrazione → Trascrivi e analizza**. Recording requires
microphone permission and a browser secure context (HTTPS or localhost); upload
remains available if recording is unsupported or denied. Review the transcript and
edit the shared form, then select **Conferma e crea ODL**. Audio analysis never creates
an ODL. Audio is temporary only; no files or audio records are retained by this slice.
Amazon Transcribe remains the future production provider described in the roadmap.

### Technician action links and Telegram Bot API

Configure `ASSIGNMENT_ACTION_SECRET` with at least 32 random bytes; generate a value
with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and save it only in
local `.env`. There is no built-in secret. Missing/short placeholder configuration
makes action-link endpoints fail closed with 503. Tokens expire after
`TECHNICIAN_ACTION_TOKEN_TTL_MINUTES=1440` (1–10080 supported); rotating the secret
invalidates all existing links. `TECHNICIAN_ACTION_BASE_URL=http://127.0.0.1:5173`
is the frontend origin, without `/tecnico`. On a smartphone use a reachable frontend
URL instead of loopback, following the Quick Tunnel flow below.
The host must serve the SPA for `/tecnico/assegnazione/*` (Vite does this locally).

1. In ODL detail, click **Assegna tecnico** to start an assignment.
2. In ODL detail, click **Invia Telegram**, or POST `/api/assignments/{id}/notify`.
3. With default `NOTIFICATION_PROVIDER=mock`, no network request occurs. The response
   reports `simulated` and includes `action_url`; **Apri link tecnico** opens it.
4. The mobile page shows only intervention details, with **Accetta intervento** and
   **Rifiuta**, followed by optional notes and confirmation. It calls the public
   endpoints with the signed token. Acceptance/rejection reuse existing routing
   transactions. No next technician means 409 and the previous attempt remains pending.
5. A successful rejection creates the next pending assignment; notification of that
   next assignment is still an explicit operator action. Dashboard and ODL detail now refresh automatically through the realtime slice below.

For actual Telegram submission, configure the root/backend `.env`:

```dotenv
NOTIFICATION_PROVIDER=telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_DEMO_CHAT_ID=
```

Create a bot through Telegram's **@BotFather**, save its token only in the backend
configuration, then open your bot on your phone and press **Start** or send a message.
Obtain your numeric chat ID from `result[].message.chat.id` using a one-off,
server-side Bot API `getUpdates` request with your token. Do not put the token in
frontend configuration, browser URLs, screenshots, or shared logs. SOLVO implements
no polling loop or Telegram webhook. See the official [Bot API](https://core.telegram.org/bots/api#getupdates).
Restart FastAPI after changing settings.

**Demo shortcut:** all technician notifications go to `TELEGRAM_DEMO_CHAT_ID`,
regardless of which technician routing selected. Technician phone numbers are not
Telegram destinations. No Technician field or database migration is added.
Production notification identity/channel work is tracked only in `docs/ROADMAP.md`.

HTTPX sends HTTPS JSON to Telegram's server-side `sendMessage` endpoint with a
10-second timeout. The message contains SOLVO, ODL code, priority, category,
fault address and the signed action URL; requester contacts are omitted. Link
previews are disabled and no inline callback buttons are used. The response includes
`provider=telegram`, the string message ID, `status=submitted`, and `action_url`.
Submission confirms API acceptance, not phone delivery or reading. Missing/invalid
configuration and provider failures return a clear 503. The default mock remains
deterministic and network-free; tests never send real messages.

#### Phone demo with Cloudflare Quick Tunnel

For same-PC testing keep `TECHNICIAN_ACTION_BASE_URL=http://127.0.0.1:5173`.
For real phone testing the base URL must be reachable from that phone. The recommended
zero-cost demo option is [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).
With `cloudflared` already available (installation is not automated here), run:

```sh
cloudflared tunnel --url http://127.0.0.1:5173
```

It prints a temporary `https://....trycloudflare.com` URL. Set the backend
`TECHNICIAN_ACTION_BASE_URL` to that exact URL, without a trailing technician path,
and restart FastAPI. Start/restart Vite from `frontend/`, allowing only the actual
hostname printed by the tunnel (replace the placeholder):

```sh
__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=your-generated-host.trycloudflare.com npm run dev
```

Vite stays bound to loopback; the tunnel forwards to it. Its existing `/api` and
`/ws` proxies reach the same single FastAPI backend, so no public backend URL or
CORS change is required. Click **Invia Telegram** again to generate a link using the
new base URL, open it on your phone, and accept or refuse; the Control Center updates
through WebSocket. Keep Vite, FastAPI and the tunnel running during the demo. A new
tunnel URL requires updating the base URL/allowed hostname and sending a new link.
Quick Tunnel is temporary development/demo access only, not production architecture.
It exposes this unauthenticated demo application: use fictional demo data and stop
the tunnel after testing. No tunnel URL is hardcoded in the repository.

Links are bearer capabilities: anyone holding one can view that assignment and act
while pending. Do not share them publicly or log them. Use HTTPS when serving beyond
localhost and redact `/api/public/assignments/*` and technician paths in access logs.
The SPA uses no-referrer and public data responses use no-store. Existing operator
APIs remain unauthenticated in this MVP: keep them on a trusted network; signed public
links do not add authorization to those separate APIs.

Notification history records provider acceptance/simulation without the token,
message body or credentials. Provider errors roll back local history and leave the
assignment unchanged. External submission and database commit are not an atomic
transaction: a timeout or commit failure can leave uncertain delivery. There is no
automatic retry; inspect the Telegram chat before explicitly resending to avoid duplicates.

### Realtime ODL updates

Run **one backend process/worker** for this MVP. `/ws/work-orders` accepts WebSocket
connections and broadcasts small invalidation events with `type`, `work_order_id`
and a UTC `timestamp`. Events contain no contact details, notes or action tokens.
Dashboard refetches its WorkOrders; detail refetches the ODL, reminders, history and
assignments only for matching IDs. The public technician page uses the same assignment
services, so its acceptance/refusal updates the operator view automatically.

Vite proxies `/ws` (including WebSocket upgrades) to the existing `VITE_API_BASE_URL`,
just as it proxies `/api`. The browser connects through its current frontend origin,
using `ws://` for HTTP and `wss://` for HTTPS. No extra environment variable is required.
Any non-Vite host must forward `/ws/work-orders` upgrades to FastAPI as well as `/api`.

A subtle Live/Riconnessione/Offline indicator shows connection state. Retries wait
3, 6, 12, then at most 15 seconds, resetting after connection. A successful connection
triggers a refetch to cover missed events. Events arriving together are grouped for
150 ms. Navigation closes the connection and cancels reconnect/refresh timers.
Manual refresh remains available. The ODL list and technician page are not subscribed.

Publishing occurs only after successful commit; failed commits and no-op changes
publish nothing. Broadcast failure never rolls back committed data. Broken/slow
clients are removed and errors logged without payloads. Events are best-effort:
there is no durable queue, replay or cross-process fan-out. The in-memory manager
is single-instance only and this unauthenticated operator feed belongs on the same
trusted network as the operator APIs. Multi-instance pub/sub and AWS scaling are
tracked in ROADMAP; neither is implemented here.

### Operator controls in ODL detail

In **Assegnazioni**, **Assegna tecnico** starts routing when the ODL has no
assignment attempts and is not CHIUSO/ANNULLATO. The backend forbids restarting
an existing chain even when no PENDING attempt remains, so ACCEPTED shows the
technician and status without a restart button.

The current PENDING attempt shows technician name, PENDING, **Invia Telegram**,
**Nessuna risposta**, and **Escala al caposquadra**. No-response advances to the
next configured technician; escalation selects an untried team leader. The
backend decides eligibility and returns a visible conflict if no candidate exists.
No operator accept/reject controls are added. Terminal ODLs hide all assignment
mutation controls, including notification. Requests disable controls while in
flight; errors are shown inline and mutations are never retried automatically.

For **Aggiungi sollecito**, configure `frontend/.env` using the real user ID
printed by the demo seed (the following value is only an example):

```dotenv
VITE_DEMO_USER_ID=1
```

This is local/demo attribution only because authentication is not implemented.
It is a public frontend value, not a secret or authenticated production identity.
There is no fallback ID. Missing/invalid values disable reminder creation; a
nonexistent database user produces the backend validation error. Restart Vite
(or rebuild a demo preview) after changing the value. Reminders remain allowed
in every ODL status, matching the existing endpoint.

Successful local actions immediately refetch assignments, reminders, history
and the ODL including `reminders_count`, and show inline feedback. Existing
WebSocket refreshes remain active. Assignment notifications still refresh history
and expose the existing technician link; sending remains an explicit action.

### Binary reference audit

`docs/design/SOLVO_Guida_Tecnica_MVP_v0.1 (2).pdf` remains an unchanged binary
reference and requires manual regeneration of its superseded notification
architecture. The explicit Telegram MVP decisions in these text documents take
precedence. The tracked PNG is the visual reference, not a transport specification.
No tracked DOCX documents are present.
