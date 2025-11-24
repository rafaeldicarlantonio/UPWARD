# UPWARD Frontend API Contract (v0.1)

This document defines the minimal API contract the frontend relies on.  
The actual backend may provide additional fields.

Base URL: `NEXT_PUBLIC_API_URL` (e.g. `https://api.upward.example.com`)

---

## 1. Chat Endpoint

### 1.1 `POST /chat`

**Purpose:**  
Submit a user message and receive a structured epistemic response.

**Request body (JSON):**

```json
{
  "sessionId": "string-uuid-or-similar",
  "message": "User question or instruction",
  "mode": "public | scholar | staff",
  "options": {
    "includeProcessTrace": true,
    "includeContradictions": true
  }
}
