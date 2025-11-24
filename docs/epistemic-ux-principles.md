
---

## 2. `docs/epistemic-ux-principles.md`

This tells Cursor *why* the UI looks like this and stops it from “simplifying” the hard parts away.

```md
# UPWARD Epistemic UX Principles

This document captures the epistemic and research-driven design principles behind the UPWARD UI.  
The frontend should treat these as constraints, not suggestions.

---

## 1. Core Philosophy

UPWARD is not “chat with an AI.”  
It is an **epistemic workspace** for working with:

- Answers
- Evidence
- Hypotheses
- Uncertainty
- Process traces (Rheomode / REDO)

Every serious interaction should make these elements visible and navigable.

---

## 2. Problems With Typical Research Tools

The UI is designed explicitly to mitigate common research-tool and epistemological issues:

- **Fragmented evidence**
  - Data scattered across tools and views.
- **Black-box reasoning**
  - Models produce outputs without traceable reasoning.
- **Context loss**
  - Snippets appear without provenance or metadata.
- **Suppression of disagreement**
  - Systems push single answers rather than structured alternative hypotheses.
- **Weak link from data to decisions**
  - Insights not clearly linked to evidence and assumptions.

UPWARD’s UI must **not** replicate these problems.

---

## 3. Design Principles

### 3.1 “Hypothesis with receipts” as the atomic unit

For research-grade answers, the atomic object is:

- a **hypothesis**
- backed by **evidence**
- wrapped in **uncertainty**

The UI should:

- Always show which hypotheses are being entertained.
- Link each hypothesis to the evidence that supports it.
- Make uncertainty and open questions explicit.

### 3.2 Evidence-centric navigation

Users must be able to move easily:

- From **evidence → all hypotheses** that use it.
- From **hypothesis → all evidence** that supports or challenges it.

This helps avoid cherry-picking and allows researchers to see how strongly a hypothesis is grounded.

### 3.3 Built-in disagreement

The UI should treat **alternative hypotheses and disagreement** as normal:

- There is rarely a single definitive answer, especially in anomalous domains.
- Hypotheses panel should visibly support multiple competing views.
- Uncertainty panel should clearly state where knowledge is thin or contested.

### 3.4 Explicit uncertainty and caveats

Uncertainty is not decoration. It is a first-class output:

- Every significant answer should include explicit uncertainty information.
- Uncertainty is not just “confidence score”; it includes:
  - unknowns
  - controversial points
  - acknowledged gaps in evidence.

### 3.5 Process transparency (Rheomode / REDO)

The reasoning process (Relevate, Evidentiate, Divide, Ordinate) should be inspectable:

- Scholars and Staff should be able to see:
  - which concepts and memories were lifted into focus,
  - which evidence was considered,
  - how the question was subdivided,
  - how the final structure was chosen.
- Process is shown in a dedicated sidebar, not hidden in logs.

Public mode can hide this by default, but it should remain accessible as an “advanced view”.

### 3.6 Mode-aware depth

Different users need different levels of detail:

- **Public:**
  - Simple view.
  - Accessible language.
  - Minimal epistemic machinery on screen.

- **Scholar:**
  - Full epistemic panels and process trace.
  - Designed for exploring competing hypotheses and evidence.

- **Staff:**
  - Scholar-level detail plus controls to:
    - update evidence status,
    - work with contradictions,
    - manage epistemic health of the corpus.

UI components should check current mode and adapt their visible detail accordingly.

---

## 4. Page-specific Epistemic Intent

### 4.1 Chat / Epistemic Workspace

Intent:

- Allow users to ask questions and see:
  - a structured answer,
  - the supporting evidence,
  - competing hypotheses,
  - uncertainties,
  - and the process trace.

UX implications:

- Assistant messages MUST have structure:
  - Answer
  - Evidence
  - Hypotheses
  - Uncertainty
- Avoid long, unstructured blocks of text.
- Sidebar process trace reinforces transparency.

### 4.2 Upload / Corpus

Intent:

- Control epistemic inputs, not just upload files.

UX implications:

- Upload form must collect epistemic metadata:
  - source type
  - domain
  - perceived reliability
  - lifecycle status
- This metadata should later appear in Evidence panels and Debug views.

### 4.3 Debug / Epistemic Control Room

Intent:

- Allow Staff/Scholar users to inspect **how the system is thinking and where it’s conflicted**.

UX implications:

- Memory lookup should expose:
  - content
  - metadata
  - relations (concepts, frames) where feasible.
- Rheomode lookup should show REDO steps.
- Contradictions list should make conflicts visible and eventually manageable.

---

## 5. Visual Tone

- Prioritize clarity over aesthetic experimentation.
- Provide a calm, professional look appropriate for research work.
- Use visual hierarchy and white space to make epistemic structure obvious at a glance.

---

## 6. Non-Goals (v1)

- No public marketing site or heavy storytelling visuals.
- No advanced graph visualizations in v1 (they can be introduced later).
- No over-engineered collaboration features (comments, presence indicators) in v1.

The main focus is: **build a frontend that makes UPWARD’s epistemic model visible and usable.**
