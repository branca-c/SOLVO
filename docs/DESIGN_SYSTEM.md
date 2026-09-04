# SOLVO Design System

## 1. Visual source

The binding visual reference is `docs/design/guida_stile_solvo_e_dashboard_ticket (1).png`. Implementations should match its light, fresh SaaS dashboard: generous white space, deep indigo navigation, aqua actions, softly elevated white cards, cool gray structure, rounded status pills, and dense but readable operational data.

## 2. Exact color tokens

### Brand and neutral palette

| Token | Hex | Use |
|---|---|---|
| `primary` | `#5B5FEF` | Brand emphasis, selected navigation, links |
| `primary-dark` | `#4548C9` | Gradient depth, pressed/strong brand states |
| `secondary-aqua` | `#18BFAE` | Main positive action, success/live accents |
| `accent-cyan` | `#38BDF8` | Informational accents, secondary data visuals |
| `background` | `#F7F8FC` | Application canvas |
| `surface` | `#FFFFFF` | Cards, table, inputs, overlays |
| `border` | `#E7E9F2` | Dividers and control/card outlines |
| `text-primary` | `#182033` | Headings and primary copy |
| `text-secondary` | `#697386` | Supporting text and metadata |

### Priority palette

| Priority | Hex |
|---|---|
| `PROGRAMMABILE` | `#64748B` |
| `BASSA` | `#3B82F6` |
| `MEDIA` | `#F59E0B` |
| `ALTA` | `#F97316` |
| `URGENTE` | `#EF4444` |

Use the priority color for a dot, icon, text, or tinted badge. Avoid large saturated fills. Text on tinted badges must meet WCAG AA contrast; darken foreground text when the exact base color is insufficient on white.

### Status semantics

Status colors are semantic derivatives, not additions to the brand palette:

| Status | Treatment |
|---|---|
| `APERTO` | Primary indigo tint and primary text |
| `IN_CORSO` | Aqua tint and aqua-dark readable text |
| `EVASO` | Cyan tint and cyan-dark readable text |
| `CHIUSO` | Cool slate tint and text |
| `ANNULLATO` | Neutral cool-gray tint and text |

Priority and status must always include a text label; color alone never carries meaning.

## 3. Typography

Use a rounded geometric sans-serif that matches the reference; `Poppins` is the preferred web font, with `Inter`, `system-ui`, and `sans-serif` fallbacks. Use 600–700 weight for titles/metrics and 400–500 for body/interface copy.

- Page title: 24–28 px, 700, tight line height.
- Section/card title: 14–18 px, 600–700.
- Body and controls: 14–16 px, 400–500.
- Table labels/metadata: 12–13 px, 500–600.
- Large metric: 26–32 px, 700.

Use sentence case for Italian copy. Controlled enum badges remain uppercase.

## 4. Shape, spacing, and elevation

- Base spacing unit: 4 px; preferred steps: 8, 12, 16, 24, 32.
- App content padding: 24–32 px desktop, 16 px compact/mobile.
- Cards/containers: 12–16 px radius, `surface`, thin `border`, very soft cool shadow.
- Inputs/buttons: about 10 px radius and minimum 44 px touch height.
- Badges: pill radius, compact horizontal padding, uppercase 11–12 px/600 label.
- Icons: simple rounded line icons, normally 18–22 px.
- Focus: visible 2 px primary outline with offset; never remove focus styling.

Shadows should separate layers without making the interface gray or heavy. Prefer border plus a low-opacity indigo/slate shadow.

## 5. Dashboard composition

### Desktop Control Center

- Fixed left sidebar, approximately 220 px wide, with a `primary-dark` to `primary` blue-indigo gradient.
- White SOLVO wordmark at the top; vertically stacked icon/label navigation.
- Active navigation appears on a translucent lighter indigo rounded rectangle.
- User identity stays at the sidebar bottom.
- Main canvas uses `background` with a welcoming header, search field, notification affordance, and aqua primary action.
- A four-card summary row uses white cards, circular tinted icons, uppercase muted labels, and strong metrics.
- "ODL recenti" is a large white table card with restrained row dividers, compact badges, assignee avatar/name, and row action menu.

Use product-relevant navigation labels such as Dashboard, ODL, Categorie/Team, and Impostazioni. Do not copy irrelevant sample-domain labels merely because they appear in the mockup.

### ODL table

Recommended columns are code, title/description, requester, category, priority, status, assigned technician, created date, and actions. At smaller widths, retain code, priority, status, and the next relevant action; move secondary content into the detail view.

Do not add SLA, deadline/scadenza derived from SLA, overdue/scaduti, or "tempo aperto" UI. The sample mockup’s deadline/overdue content is illustrative dashboard styling, not SOLVO scope.

### Mobile technician experience

Use a single-column white-card layout, concise facts, priority/status badges, and persistent or clearly visible full-width actions. `ACCETTA` uses aqua; `RIFIUTA` is a lower-emphasis outlined/destructive action. Refusal opens only an optional notes input. Work-performed text is prominent before `EVASO`.

## 6. Components and states

- Buttons: primary aqua, secondary indigo/outlined, tertiary text, destructive only where consequences require it.
- Inputs: white surface, cool border, primary focus ring, inline error plus summary where appropriate.
- Cards: standard content, metric, urgent alert, and empty-state variants.
- Feedback: skeleton/loading, empty, inline validation, retryable provider error, permission error, offline/reconnecting, and success confirmation.
- Urgent people-risk alert: restrained urgent red plus icon and explicit language; include the team-lead call action and emergency-service disclaimer.
- Motion: brief 150–200 ms feedback; honor `prefers-reduced-motion`.

## 7. Accessibility and responsive behavior

- Target WCAG 2.1 AA contrast and keyboard operation.
- Provide accessible names for icon-only controls and status announcements for asynchronous changes.
- Keep tap targets at least 44 × 44 px.
- Tables require semantic headers; use cards/list rows on narrow screens rather than horizontal compression.
- Do not communicate priority, status, errors, or live changes with color alone.

