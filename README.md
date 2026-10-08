# SOLVO

SOLVO is an AI-assisted work-order and facility service desk. A requester describes a fault by text or audio, reviews an editable structured ODL (Ordine di Lavoro) draft, and confirms it. Deterministic backend rules route the confirmed ODL to technicians, while operators monitor progress in a real-time Control Center.

The delivered public demo includes the requester, technician, and operator flows, backed by FastAPI, SQLAlchemy/Alembic, and PostgreSQL. It is an MVP public demo, not a production-ready deployment: authentication/authorization, API-contract, hardening, and automated end-to-end coverage still have explicit gaps.

The normal requester/operator demo surface is protected by a single shared
`SOLVO_DEMO_ACCESS_KEY`, entered manually by a tester and held only in that browser
session. This is a small demo gate, not production authentication or authorization.
The canonical demo key is configured only server-side and is never hardcoded in the
frontend bundle; the tester-entered copy is held only in sessionStorage.
Signed technician action links and the Telegram webhook keep their separate security
mechanisms and do not require the demo key.

When `SOLVO_DEMO_SESSION_ENABLED=true`, successful gate entry automatically acquires
one exclusive database-backed demo lease. A second browser sees “Demo temporaneamente
in uso” until the lease is released or its configurable idle timeout expires. The
browser keeps the random lease token only in `sessionStorage`; the database stores
only its hash. Ending the session atomically removes runtime ODL/workflow data and
the session Telegram link while preserving reference data and permanent technician
Telegram bindings. `SOLVO_DEMO_SESSION_IDLE_MINUTES=10` is the default lease timeout.

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
- Frontend: React + TypeScript + Vite; backend: FastAPI + Pydantic + SQLAlchemy + Alembic.
- Database: PostgreSQL (Neon for the public demo); realtime WebSocket updates are in-memory and single-instance.
- Public-demo AI uses Groq: `openai/gpt-oss-120b` for text extraction and `whisper-large-v3-turbo` for audio transcription.
- Telegram Bot API delivers technician notifications and supports private technician self-service binding; AWS integrations are deferred.
- No SLA or "tempo aperto" is part of the MVP.

## Public demo and current deployment

The public frontend is available at https://solvo-frontend.onrender.com. Its FastAPI backend runs as a Render Web Service and its demo PostgreSQL database is Neon. This deployment no longer depends on a developer PC or Cloudflare Quick Tunnel; Quick Tunnel remains documented below only for local phone-access testing.

The current public workflow is: create an ODL, assign a technician, handle rejection and deterministic escalation when needed, send a Telegram notification, open a signed technician action link, accept the intervention, and move the ODL from `APERTO` to `IN_CORSO`. This flow has been manually verified publicly, including two rejections/escalations before a Telegram action-link acceptance.

Delivery status: Steps 0, 2, 4, 5, and 6 are delivered. Steps 1 and 3 are materially delivered with explicit remaining gaps. Step 7 (hardening and demo) is current. AWS deployment remains deferred and is not the current deployment.

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

## Public-demo reset

The backend-only maintenance command below removes demo runtime ODL data and
idempotently restores missing demo reference data. It is not an HTTP or frontend
feature, and requires the explicit destructive confirmation flag:

```sh
python -m app.scripts.reset_demo --confirm
```

By default, the command preserves technician Telegram bindings. To clear only
those bindings while retaining technician identity and routing configuration:

```sh
python -m app.scripts.reset_demo --confirm --clear-telegram-bindings
```

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

Reminder creation requires JSON `{"created_by": 1, "text": "Richiesta aggiornamenti dopo il sopralluogo"}` identifying an existing user.
Text is required, trimmed, and limited to 1–2000 characters; blank text returns 422.
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
La pagina Tecnici mostra i dati di instradamento e permette di modificare i contatti. Il dettaglio mostra ODL, solleciti,
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
`/api` a FastAPI sulla stessa origine. Questa è la configurazione di sviluppo/preview
locale; per il deployment pubblico corrente, vedi **Public demo and current deployment**.
I test Vitest verificano componenti, form, transizioni, conteggi,
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
Altri provider diversi da `mock`, `fake` e `ollama`, compreso `bedrock`, restituiscono attualmente 503; non viene
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

### Audio-assisted intake (mock or real local transcription)

Install updated backend dependencies with `backend/.venv/bin/python -m pip install -r backend/requirements.txt`.
Set `TRANSCRIPTION_PROVIDER=mock` (legacy `fake` also accepted),
`TRANSCRIPTION_MOCK_TEXT="Perdita di acqua dal tubo del bagno."` and
`MAX_AUDIO_UPLOAD_MB=10` in `.env`. The configurable server limit is 1–25 MiB;
the browser conservatively allows at most 10 MiB. No AWS credentials are required.
In mock mode every accepted file returns the configured demonstration text, **not recognized speech**.
The transcript feeds the existing AI draft pipeline (selected via `AI_PROVIDER=mock|ollama`).

Under **Nuovo ODL → Assistito da AI**, upload WebM/WAV/MP3/MP4 or choose
**Registra audio → Ferma registrazione → Trascrivi e analizza**. Recording requires
microphone permission and a browser secure context (HTTPS or localhost); upload
remains available if recording is unsupported or denied. Review the transcript and
edit the shared form, then select **Conferma e crea ODL**. Audio analysis never creates
an ODL. Audio is temporary only; no files or audio records are retained by this slice.
Amazon Transcribe is an optional future cloud provider described in the roadmap, not implemented.

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
# Optional fallback for an unlinked technician; keep server-side.
TELEGRAM_DEMO_CHAT_ID=
TELEGRAM_BOT_USERNAME=
TELEGRAM_BINDING_SECRET=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_BINDING_TOKEN_TTL_MINUTES=15
```

Create a bot through Telegram's **@BotFather** and keep all token, webhook, and
binding secrets only in backend configuration. Do not put them in frontend
configuration, browser URLs, screenshots, or shared logs. Restart FastAPI after
changing settings.

Private per-technician Telegram binding is implemented. In the public **Tecnici**
page, **Collega Telegram** creates a signed, expiring bot deep link; its binding TTL
is currently 15 minutes. The protected Telegram webhook processes a private `/start`
and stores the chat destination server-side. The frontend receives only the
`telegram_linked` boolean, never `telegram_chat_id`. One Telegram account/chat can
be linked to only one technician, and there is no public unlink UI. Notifications
prefer the linked technician's private chat; `TELEGRAM_DEMO_CHAT_ID` remains an
optional server-side fallback for an unlinked technician. Technician phone numbers
are not Telegram destinations.

HTTPX sends HTTPS JSON to Telegram's server-side `sendMessage` endpoint with a
10-second timeout. The message contains SOLVO, ODL code, priority, category,
fault address and the signed action URL; requester contacts are omitted. Link
previews are disabled and no inline callback buttons are used. The response includes
`provider=telegram`, the string message ID, `status=submitted`, and `action_url`.
Submission confirms API acceptance, not phone delivery or reading. Missing/invalid
configuration and provider failures return a clear 503. The default mock remains
deterministic and network-free; tests never send real messages.

#### Local phone testing with Cloudflare Quick Tunnel

For same-PC testing keep `TECHNICIAN_ACTION_BASE_URL=http://127.0.0.1:5173`.
For local phone testing the base URL must be reachable from that phone. A temporary
development option is [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).
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
**Technician phone is editable real contact data and is not a Telegram destination.**
Telegram notifications prefer the technician's private server-side binding, with an
optional demo-chat fallback when the technician is unlinked. No authentication or
new notification channels are included.

For production archive/soft-delete and audit-retention considerations, see the future deletion evolution in `docs/ROADMAP.md`. Run `alembic upgrade head` before using notes. The PDF guide is unchanged pending application validation.


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


## Real local audio transcription

Install the updated backend dependencies in the virtual environment (this downloads
Python packages, not a Whisper model):

```sh
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

To recognize the actual recorded/uploaded speech, set these root `.env` values and
restart FastAPI:

```dotenv
TRANSCRIPTION_PROVIDER=local_whisper
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=auto
WHISPER_LANGUAGE=it
WHISPER_BEAM_SIZE=3
AI_PROVIDER=mock
```

`small` is the conservative multilingual development default. Larger models can
improve accuracy but consume more RAM/VRAM and processing time; `base` is a lighter
alternative. Local recognition has no per-request API cost. The first request may
need network access to download model files into the library’s user cache (outside
the repository), and takes longer while the model loads. Subsequent requests reuse
the model in the same backend process; cached models can run offline. Restarting
reloads the model into memory. Use a local converted-model directory as
WHISPER_MODEL_SIZE if model files have already been provisioned offline.
WHISPER_BEAM_SIZE is an integer >= 1; the default is 3 for benchmarking.
Set it to 5 to compare against the previous decoding baseline. Restart the backend
after changing configuration.

`auto` probes CUDA availability, tries the GPU when available and falls back to
CPU/int8 if GPU initialization or inference fails. No machine-specific CUDA paths
are set. CPU does not require CUDA; force `WHISPER_DEVICE=cpu` with
`WHISPER_COMPUTE_TYPE=int8` when desired. Explicit `cuda` reports configuration/runtime
failure instead of silently switching. For a fixed device, compute types supported
by CTranslate2 can be configured; Italian is default and WHISPER_LANGUAGE can select
another supported language code.

MediaRecorder’s existing WebM/Opus upload is unchanged. PyAV decodes real audio bytes
in a closed in-memory stream, including supported WAV, MPEG/MP3 and MP4 codecs.
SOLVO retains no permanent audio file. The transcript passes through the original
draft extraction/category resolution; review and explicit confirmation are still
required before any ODL is created. The UI shows Trascrizione locale for local
recognition and a simulated/demo warning only for mock responses.

Empty/unreadable audio, no recognized speech, missing dependencies/model files,
initialization and inference failures return readable errors without tracebacks.
`TRANSCRIPTION_PROVIDER=mock` remains the deterministic test/demo option using
TRANSCRIPTION_MOCK_TEXT. Automated tests stub the Whisper runtime; they never
fetch a model. Amazon Transcribe is not implemented. PDF guide remains unchanged.
Provider API reference: https://github.com/SYSTRAN/faster-whisper.


## Estrazione semantica locale con Ollama

`AI_PROVIDER=mock` mantiene l'estrazione deterministica per test/demo, senza rete.
Per l'uso locale reale, avvia Ollama e scegli un modello già installato tramite
`ollama list`; SOLVO non scarica né esegue pull di modelli. Configura la `.env`
alla radice e riavvia FastAPI:

```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=<nome-esatto-del-modello-gia-installato>
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_KEEP_ALIVE=30m
```

OLLAMA_MODEL è obbligatorio con Ollama; il timeout deve essere positivo e finito.
Il backend chiama `/api/chat` con HTTPX e lo schema JSON di `ExtractedWorkOrder`,
poi valida nuovamente con Pydantic. Nessun fallback automatico al mock.
Le categorie sono i nomi letti dai record Category, forniti nel prompt e nello
schema; solo il backend risolve un nome univoco in category_id.

Whisper riconosce il parlato (speech-to-text); Ollama estrae i campi e sintetizza
il problema tecnico. Sono responsabilità separate. Per l'intera pipeline reale
usa anche `TRANSCRIPTION_PROVIDER=local_whisper` con le opzioni Whisper sopra.
Testo digitato e transcript condividono la stessa estrazione: dati del richiedente,
telefono, email, indirizzo, categoria, priorità e descrizione compilano il modulo
esistente. Dati mancanti restano vuoti/null con avvisi; una descrizione mancante
resta vuota, senza fallback al transcript. Completa, modifica e premi
**Conferma e crea ODL**: solo allora viene chiamato il normale endpoint di creazione.

Il prompt italiano vieta dati inventati, markdown, commenti e istruzioni del
segnalante; richiede una sintesi tecnica senza nomi, telefono, email o indirizzo.
Il backend esclude contatti/indirizzi non rintracciabili nel testo (consentendo
normalizzazioni di punteggiatura/spazi). Se la sintesi Ollama contiene un valore
esatto estratto di contatto/indirizzo, la risposta è rifiutata, senza manipolare
frasi automaticamente. Il controllo è conservativo e non verifica tutte le
possibili parafrasi. Tutti i dati richiedono comunque revisione umana.

Ollama non raggiungibile, modello non configurato/non disponibile e timeout
producono messaggi leggibili (503); JSON malformato, schema invalido o sintesi
con dati ripetuti producono 502. Non sono esposti traceback o risposte grezze.
I test usano HTTP simulato e non richiedono Ollama. Amazon Bedrock resta un
provider cloud opzionale futuro, descritto in `docs/ROADMAP.md`; nessuna AWS
è implementata e il PDF non viene rigenerato.


## Hybrid draft classification

Ollama remains the primary semantic extractor. After ExtractedWorkOrder validation
and normal category resolution, build_draft fills missing/unresolved categories
and reconciles priority using pure domain rules on the original request or
transcript. Valid category proposals are preserved. Provider errors and invalid
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

Priority reconciliation uses the original report, never the generated description.
Explicit immediate danger, human safety risk, trapped people or an emergency takes
precedence over any provider priority and yields URGENTE. Complete service blockage
without explicit danger yields ALTA. A provider URGENTE is lowered only for narrowly
recognized, unambiguous blockage reports (including explicit safety denials);
unknown additional wording preserves URGENTE because lexical silence cannot rule
out danger. Otherwise a missing/null priority uses priority_fallback(), and other
provider values are preserved. Every changed value, including a filled missing
priority, receives an existing review warning. Text and audio share these rules.

Priority rules propose URGENTE only for explicit trapped people, immediate danger,
fire/smoke, gas leak, grave electrical risk or flooding/strong leakage with explicit
immediate damage risk. The word “urgente” alone is insufficient. ALTA covers a
blocked/nonrestarting elevator and explicit complete service outages; MEDIA covers
clear faults/degradation. BASSA and PROGRAMMABILE require explicit minor-discomfort
or planned-maintenance wording. Danger and complete blockage take precedence over
minor/planned wording. Insufficient evidence leaves priority null.

Paired quoted passages and recognizable example clauses are excluded. Simple
clause-local negation checks suppress obvious negated signals; this is conservative
lexical matching, not comprehensive language understanding. Ambiguity, unavailable
categories and insufficient evidence retain manual-selection warnings. Existing
warnings identify values supplied by deterministic rules without adding provenance
fields or database storage. Description handling remains unchanged: the LLM technical
summary is primary and missing summaries stay empty. Human review and explicit
confirmation remain mandatory; analysis only reads the database and creates no ODL.
No frontend, schema, migration, Whisper, Telegram or AWS changes are required.
The technical PDF is not regenerated.


`OLLAMA_KEEP_ALIVE` (default `30m`) is passed as the top-level `keep_alive` field
to Ollama `/api/chat`, retaining the selected model after requests to reduce reload
latency during subsequent use. It does not preload, pull or download models and
does not change `OLLAMA_MODEL` (keep `qwen2.5:7b`) or `OLLAMA_TIMEOUT_SECONDS`.
The first request after unloading still incurs model loading.

INFO application logs (`uvicorn.error.solvo.timing`) record `stage`, `duration_ms`
and `outcome` for Ollama HTTP requests and total draft extraction. Audio requests
also record transcription, extraction and total audio draft durations. Transcription
timing wraps the existing provider call, including Whisper when selected. Logs
contain no request/transcript/output content; timings are not added to API responses.
