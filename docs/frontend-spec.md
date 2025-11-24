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
