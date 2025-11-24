# UPWARD Frontend Specification

Version: 0.1  
Owner: Rafael / UPWARD

## 1. Purpose

This document defines the initial version of the UPWARD frontend:

- Target users for v1: internal **Scholar** and **Staff** users, plus a basic **Public** view.
- Primary goal: provide a usable **epistemic console**, not a generic chat UI.
- Focus: expose **answers, evidence, hypotheses, uncertainty, and process (REDO)** in an inspectable way.

This spec is a source of truth for the frontend implementation. Code and UX should follow this document unless explicitly updated.

---

## 2. Technical Stack

- Framework: **Next.js** (App Router, TypeScript)
- Styling: **Tailwind CSS**
- UI components: **shadcn/ui** (Cards, Buttons, Inputs, Dialogs, Toasts)
- State / data fetching:
  - Local state via React
  - Server communication via `fetch` or React Query/SWR (choice can be made at implementation time)
- API:
  - Backend: FastAPI (UPWARD / SUAPS backend)
  - Base URL: provided via `NEXT_PUBLIC_API_URL` env var

---

## 3. Top-level Routes

All routes live under `app/` (Next.js App Router):

- `/chat`  
  Primary epistemic workspace. Core interaction surface with UPWARD.

- `/upload`  
  Upload and enrich corpus material with epistemic metadata.

- `/debug`  
  Epistemic control room for inspecting memories, Rheomode runs, contradictions, etc.

Optional: `/` can redirect to `/chat`.

---

## 4. Global Concepts

### 4.1 Mode

Three modes control **depth** and **visibility** of epistemic details:

- `public`
  - Simple answer and minimal evidence list.
  - Hide most process / internals by default.

- `scholar`
  - Full epistemic view: answer, hypotheses, evidence, uncertainty, process trace.
  - Designed for research workflows.

- `staff`
  - Everything Scholar has, plus controls for managing epistemic status (e.g. marking evidence as deprecated, reviewing contradictions).

The current mode is:

- Stored in a global context (e.g. `ModeContext`).
- Selectable via a dropdown in the top navigation.
- Sent as part of the payload for `/chat`.

### 4.2 Session

Each active conversation has a `sessionId` (string / UUID):

- Stored in page state or localStorage.
- Included in every `/chat` call to maintain continuity.
- The UI does not manage session expiry; backend is responsible.

### 4.3 Core Data Types (frontend)

These types are implemented in `lib/types.ts` and are used across the app.

```ts
export type Mode = 'public' | 'scholar' | 'staff';

export interface EvidenceItem {
  id: string;
  title: string;
  sourceType: string;          // e.g. "sensor_report", "academic_paper", "witness_interview"
  date?: string;               // ISO string
  reliability?: 'low' | 'medium' | 'high';
  status?: 'new' | 'under_review' | 'accepted' | 'deprecated';
  snippet?: string;
  originSummary?: string;      // short description of provenance/origin
}

export interface Hypothesis {
  id: string;
  label: string;              // short name for the hypothesis
  description: string;        // 1–3 sentence explanation
  supportLevel: 'speculative' | 'plausible' | 'strong';
  evidenceIds: string[];      // IDs of EvidenceItem used to support it
  notes?: string;
}

export interface ProcessTrace {
  relevate: string[];         // key concepts / frames lifted into focus
  evidentiate: EvidenceItem[]; 
  divide: string[];           // list of sub-questions / aspects
  ordinate: string;           // textual description of final ordering/structure
}

export interface ChatResponse {
  answer: string;             // main explicate-level answer
  evidence: EvidenceItem[];
  hypotheses: Hypothesis[];
  uncertainty: string;        // summary of caveats / unknowns / disputes
  processTrace?: ProcessTrace;
  mode: Mode;
  // Optional additional fields:
  sessionId?: string;
  contradictionsCount?: number;
}
5. Layout & Navigation
5.1 Global Layout

Shared across all pages:

Top navigation bar:

App title: UPWARD Console

Mode selector (ModeContext): Public / Scholar / Staff

Navigation links: Chat, Upload, Debug

Content area:

Page header (title + description)

Main content (page-specific)

5.2 Chat Page Layout (/chat)

The Chat page is the primary workspace.

Layout:

Left panel: Conversation

List of messages (user + assistant)

Each assistant message renders the epistemic structure

Bottom: Composer

Multiline input + “Send” button

Enter sends, Shift+Enter adds newline

Right panel: Process sidebar

REDO (Relevate, Evidentiate, Divide, Ordinate)

Only visible in scholar and staff modes by default

Assistant message structure

Each assistant message should render:

Answer Panel

Clear title: “Answer”

Main textual answer.

Tone can vary by mode:

Public: simpler phrasing.

Scholar/Staff: more technical allowed.

Evidence Panel

Title: “Evidence”

List of EvidenceItem with:

title

sourceType

date

reliability and status (if present)

Each item:

expandable to view snippet and originSummary

Should support filtering by sourceType or reliability in v2.

Hypotheses Panel

Title: “Hypotheses”

For each Hypothesis:

label

supportLevel (visual tag)

description

small badge with number of supporting evidence items

Should allow expanding to show which EvidenceItem objects support the hypothesis.

Uncertainty Panel

Title: “Uncertainty & Caveats”

Show uncertainty text from ChatResponse.

Explicitly communicates:

unknowns

contested points

gaps in data

Mode-dependent visibility

Public mode

Show: Answer, condensed Evidence, short Uncertainty.

Hide: Hypotheses panel by default (optional “show more detail” toggle).

Hide: Process sidebar.

Scholar mode

Show all panels: Answer, Evidence, Hypotheses, Uncertainty.

Show: Process sidebar.

Staff mode

Same as Scholar, plus (in future):

controls for setting evidence status (accepted/deprecated)

quick links to contradictions related to the answer.

Process Sidebar (REDO)

In modes scholar and staff, the right sidebar shows processTrace structured as:

Section: Relevate

List of key concepts / frames (strings).

Section: Evidentiate

Evidence list, possibly mirroring main Evidence panel but in more compact form.

Section: Divide

Bullet list of sub-questions / aspects.

Section: Ordinate

Paragraph explaining the final structure / ordering.

If processTrace is not present but a rheomodeRunId exists in the API response (field can be introduced later), the UI may call a debug endpoint to fetch details.

6. Upload Page (/upload)

Purpose: ingest new materials into the system with epistemic metadata.

Layout:

Page header: “Upload & Enrich Corpus”

Main card: Upload form

Secondary area: Recent uploads table

6.1 Upload form

Fields:

File input (single file for v1)

Epistemic metadata:

Source type (select):

e.g. sensor_report, gov_document, academic_paper, witness_interview, news_article, internal_note, other.

Domain (free text or select, e.g. “radar”, “optical”, “testimony”, etc.)

Reliability (select): low, medium, high

Lifecycle status (select): new, under_review, accepted, deprecated

Submit button: “Upload”

Behavior:

On submit:

Upload file via /upload endpoint.

Once upload succeeds, send metadata to an appropriate endpoint (e.g. /memories/upsert), associating the file with epistemic attributes.

Show success / error feedback via toast.

6.2 Recent uploads table

Columns:

Filename

Source type

Reliability

Status

Uploaded at

Functional requirements:

Simple table is enough for v1.

Clicking a row may later open a detail view.

7. Debug Page (/debug)

Purpose: give Staff/Scholar users a way to inspect internal state.

Sections (vertical stack):

Memory Lookup

Input: memory ID

Button: “Lookup memory”

Output:

JSON view or formatted view:

content snippet

epistemic metadata

related concepts / frames

Rheomode Run Lookup

Input: run ID

Button: “Lookup Rheomode run”

Output:

Relevate, Evidentiate, Divide, Ordinate sections

Contradictions (v1 minimal view)

Table listing known contradictions:

ID

Claim A (short)

Claim B (short)

Status (open/resolved)

Later: link to detailed view

The Debug page can be technically accessible to all modes but navigation entry may be visually emphasized for Staff.

8. Error, Loading, and Empty States

Chat:

While waiting for /chat response:

show a loading skeleton or a subtle spinner in place of the panels.

On error:

show a toast + small inline message in the latest assistant slot.

Upload:

Show progress or simple “Uploading…” state if upload takes time.

On error:

highlight the form and show error text.

Debug:

When no result yet: show helpful empty state text (“Enter an ID to inspect.”).

9. Visual & Interaction Guidelines

Use a consistent 8px spacing scale (e.g. p-2, p-4, p-6).

Use a single primary accent color (derived from shadcn theme).

Typography:

Titles: text-xl or text-2xl, semibold.

Section headers: text-sm or text-base, medium.

Body: text-sm or text-base.

Avoid unnecessary visual clutter; prioritize clear hierarchy.
