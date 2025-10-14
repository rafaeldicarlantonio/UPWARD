# router/chat.py
import os
import json
import datetime
import time
from uuid import uuid4
from typing import Optional, List, Dict, Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, model_validator
from openai import OpenAI

from vendors.supabase_client import get_client
from vendors.pinecone_client import get_index, safe_query
from ingest.pipeline import normalize_text
from memory.autosave import apply_autosave
from guardrails.redteam import review_answer
from auth.light_identity import ensure_user  # <-- attribution helper
from memory.graph import expand_entities
from extractors.signals import extract_signals_from_text  # <-- NEW: fallback extractor
from core.selection import SelectionFactory
from core.packing import pack_with_contradictions
from core.ledger import log_chat_request
from feature_flags import get_feature_flag

router = APIRouter()
client = OpenAI()


# ---------- Models ----------
class ChatReq(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None
    role: Optional[Literal["researcher", "staff", "director", "admin"]] = None
    preferences: Optional[Dict[str, Any]] = None
    debug: bool = False

    # allow unknown fields instead of 422'ing
    model_config = ConfigDict(extra="ignore")

    # automatically create a prompt from messages[] if none is provided
    @model_validator(mode="before")
    def ensure_prompt(cls, values):
        if isinstance(values, dict) and not values.get("prompt"):
            msgs = values.get("messages") or []
            user_bits = [m.get("content", "") for m in msgs if m.get("role") == "user"]
            if user_bits:
                values["prompt"] = " ".join(user_bits)[:4000]
        if isinstance(values, dict) and not values.get("prompt"):
            raise ValueError("prompt or messages is required")
        return values

class ChatResp(BaseModel):
    session_id: str
    answer: str
    citations: List[str]
    guidance_questions: List[str]
    autosave: Dict[str, Any]
    redteam: Dict[str, Any]
    metrics: Dict[str, Any]


# ---------- Helpers ----------
def _auth(x_api_key: Optional[str]):
    expected = os.getenv("X_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _embed(text: str) -> List[float]:
    kwargs: Dict[str, Any] = {"model": os.getenv("EMBED_MODEL", "text-embedding-3-small"), "input": text}
    dim = os.getenv("EMBED_DIM")
    if dim:
        kwargs["dimensions"] = int(dim)
    er = client.embeddings.create(**kwargs)
    return er.data[0].embedding


def _retrieve(sb, index, query: str, top_k_per_type: int = 8) -> List[Dict[str, Any]]:
    vec = _embed(query)
    namespaces = ["semantic", "episodic", "procedural"]
    hits: List[Dict[str, Any]] = []

    for ns in namespaces:
        res = safe_query(index, vector=vec, top_k=top_k_per_type, include_metadata=True, namespace=ns)
        for m in res.matches:
            md = m.metadata or {}
            mem_id = (md.get("id") or (m.id or "")).replace("mem_", "")
            if not mem_id:
                continue
            hits.append({"memory_id": mem_id, "namespace": ns, "score": float(m.score or 0.0)})

    ids = list({h["memory_id"] for h in hits})
    by_id: Dict[str, Dict[str, Any]] = {}
    if ids:
        rows = (
            sb.table("memories")
            .select("id,type,title,tags,created_at")
            .in_("id", ids)
            .limit(len(ids))
            .execute()
        )
        data = rows.data if hasattr(rows, "data") else rows.get("data") or []
        by_id = {r["id"]: r for r in data}

    out: List[Dict[str, Any]] = []
    for h in hits:
        r = by_id.get(h["memory_id"])
        if not r:
            continue
        out.append(
            {
                "id": r["id"],
                "type": r["type"],
                "title": r.get("title"),
                "tags": r.get("tags") or [],
                "created_at": r.get("created_at"),
                "score": h["score"],
            }
        )

    out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return out[:12]


def _pack_context(sb, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return []

    ids = [it["id"] for it in items]
    text_col = (os.getenv("MEMORIES_TEXT_COLUMN", "text")).strip().lower()

    # Only fetch what actually exists in 'memories'
    rows = sb.table("memories").select(f"id,title,type,{text_col}") \
              .in_("id", ids).limit(len(ids)).execute()

    data = rows.data if hasattr(rows, "data") else rows.get("data") or []
    by_id = {r["id"]: r for r in data}

    out: List[Dict[str, Any]] = []
    for it in items:
        r = by_id.get(it["id"])
        if not r:
            continue

        mem_type = (r.get("type") or "semantic").upper()
        raw_text = r.get(text_col) or ""
        norm_text = normalize_text(raw_text)

        # Label the text with its memory type
        labeled_text = f"[{mem_type} MEMORY] {norm_text}"

        out.append({
            "id": it["id"],
            "title": r.get("title") or "",
            "text": labeled_text,
            "type": mem_type
        })

    return out


def _answer_json(prompt: str, context_str: str, contradictions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    sys = """You are SUAPS Brain. Be concise and specific. Mentor tone: strategic, supportive.
    Always ground answers in SUAPS data. Cite the memory IDs you used.

    You will see different types of memory in context:
    - [SEMANTIC MEMORY]: definitions, background knowledge.
    - [EPISODIC MEMORY]: time-stamped events, meetings, decisions.
    - [PROCEDURAL MEMORY]: rules, SOPs, how-to steps.

    Use each type appropriately: semantic for explanations, episodic for timelines, procedural for rules.

    Return STRICT JSON only with this schema:
    {...}
    """

    # Build context with optional contradictions section
    context_data = {"question": prompt, "context": context_str}
    
    # Add contradictions section if enabled and contradictions exist
    if contradictions and get_feature_flag("retrieval.contradictions_pack", default=False):
        contradictions_text = _format_contradictions(contradictions)
        if contradictions_text:
            context_data["contradictions"] = contradictions_text

    user = json.dumps(context_data)
    r = client.chat.completions.create(
        model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0,
    )
    raw = r.choices[0].message.content or "{}"
    return json.loads(raw)


def _format_contradictions(contradictions: List[Dict[str, Any]]) -> str:
    """Format contradictions for inclusion in model input."""
    if not contradictions:
        return ""
    
    formatted = ["CONTRADICTIONS DETECTED:"]
    for i, contradiction in enumerate(contradictions, 1):
        formatted.append(f"{i}. Subject: {contradiction.get('subject', 'Unknown')}")
        formatted.append(f"   Claim A: {contradiction.get('claim_a', '')[:100]}...")
        formatted.append(f"   Claim B: {contradiction.get('claim_b', '')[:100]}...")
        formatted.append(f"   Type: {contradiction.get('contradiction_type', 'unknown')}")
        formatted.append(f"   Confidence: {contradiction.get('confidence', 0.0):.2f}")
        formatted.append("")
    
    return "\n".join(formatted)



# ---------- Route ----------
@router.post("/chat", response_model=ChatResp)
def chat_chat_post(
    body: ChatReq,
    x_api_key: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),  # attribution header
):
    _auth(x_api_key)
    sb = get_client()
    index = get_index()
    t0 = datetime.datetime.utcnow()

    # Resolve/ensure user (best-effort)
    author_user_id = ensure_user(sb=sb, email=x_user_email)

    # Ensure a session id
    session_id = body.session_id
    if not session_id:
        # Try DB-generated id
        payload = {"title": None}
        if author_user_id:
            payload["user_id"] = author_user_id
        try:
            sb.table("sessions").insert(payload).execute()
            sel = sb.table("sessions").select("id").order("created_at", desc=True).limit(1).execute()
            data = sel.data if hasattr(sel, "data") else sel.get("data") or []
            if data:
                session_id = data[0]["id"]
        except Exception:
            # Local fallback
            session_id = str(uuid4())

    # Retrieval - use new dual retrieval system if enabled
    retrieval_start = time.time()
    use_dual_retrieval = get_feature_flag("retrieval.dual_index", default=False)
    use_contradictions = get_feature_flag("retrieval.contradictions_pack", default=False)
    use_liftscore = get_feature_flag("retrieval.liftscore", default=False)
    
    # Initialize default values
    retrieved_chunks = []
    contradictions = []
    contradiction_score = 0.0
    lift_score = None
    selection_result = None
    retrieval_error = None
    
    if use_dual_retrieval:
        # Use new dual retrieval system with graceful fallback
        try:
            print(f"Using dual retrieval system (flags: dual_index={use_dual_retrieval}, contradictions={use_contradictions}, liftscore={use_liftscore})")
            
            # Create selector based on feature flags
            selector = SelectionFactory.create_selector()
            
            # Generate embedding
            embedding = _embed(body.prompt)
            
            # Select content using the appropriate strategy
            selection_result = selector.select(
                query=body.prompt,
                embedding=embedding,
                caller_role=body.role,
                explicate_top_k=int(os.getenv("TOPK_PER_TYPE", "16")),
                implicate_top_k=8
            )
            
            # Pack with contradiction detection if enabled
            if use_contradictions:
                try:
                    packing_result = pack_with_contradictions(
                        context=selection_result.context,
                        ranked_ids=selection_result.ranked_ids,
                        top_m=10
                    )
                    retrieved_chunks = packing_result.context
                    contradictions = packing_result.contradictions
                    contradiction_score = packing_result.contradiction_score
                    print(f"Contradiction detection: found {len(contradictions)} contradictions")
                except Exception as e:
                    print(f"Contradiction detection failed, proceeding without: {e}")
                    retrieved_chunks = selection_result.context
                    contradictions = []
                    contradiction_score = 0.0
            else:
                retrieved_chunks = selection_result.context
                contradictions = []
                contradiction_score = 0.0
            
            # Calculate lift score if using LiftScore ranking
            if use_liftscore:
                try:
                    lift_scores = [item.get("lift_score", 0.0) for item in retrieved_chunks if "lift_score" in item]
                    if lift_scores:
                        lift_score = sum(lift_scores) / len(lift_scores)
                        print(f"LiftScore calculation: average={lift_score:.3f}")
                except Exception as e:
                    print(f"LiftScore calculation failed: {e}")
                    lift_score = None
            
            print(f"Dual retrieval successful: {len(retrieved_chunks)} chunks retrieved")
            
        except Exception as e:
            retrieval_error = str(e)
            print(f"Dual retrieval failed ({retrieval_error}), falling back to legacy retrieval")
            # Fallback to legacy retrieval
            try:
                retrieved_meta = _retrieve(
                    sb,
                    index,
                    body.prompt,
                    top_k_per_type=int(os.getenv("TOPK_PER_TYPE", "8"))
                )
                retrieved_chunks = _pack_context(sb, retrieved_meta)
                contradictions = []
                contradiction_score = 0.0
                lift_score = None
                selection_result = None
                print(f"Legacy retrieval fallback successful: {len(retrieved_chunks)} chunks retrieved")
            except Exception as legacy_error:
                print(f"Legacy retrieval also failed: {legacy_error}")
                # Final fallback - return empty results
                retrieved_chunks = []
                contradictions = []
                contradiction_score = 0.0
                lift_score = None
                selection_result = None
    else:
        # Use legacy retrieval
        print("Using legacy retrieval system")
        try:
            retrieved_meta = _retrieve(
                sb,
                index,
                body.prompt,
                top_k_per_type=int(os.getenv("TOPK_PER_TYPE", "8"))
            )
            retrieved_chunks = _pack_context(sb, retrieved_meta)
            contradictions = []
            contradiction_score = 0.0
            lift_score = None
            selection_result = None
            print(f"Legacy retrieval successful: {len(retrieved_chunks)} chunks retrieved")
        except Exception as e:
            print(f"Legacy retrieval failed: {e}")
            # Final fallback - return empty results
            retrieved_chunks = []
            contradictions = []
            contradiction_score = 0.0
            lift_score = None
            selection_result = None
    
    retrieval_time = (time.time() - retrieval_start) * 1000  # Convert to milliseconds

    # 🔗 Graph Expansion (3 hops) - non-fatal
    try:
        graph_neighbors = expand_entities(sb, retrieved_chunks, max_hops=3, max_neighbors=10, max_per_entity=3)
        retrieved_chunks.extend(graph_neighbors)
    except Exception as e:
        # non-fatal: log or ignore if graph expansion fails
        print("Graph expansion failed:", e)

    # Build context string with memory-type labels
    context_for_llm = "\n".join(chunk["text"] for chunk in retrieved_chunks)

    # Collect just the IDs (for schema validation of "citations")
    context_ids = [chunk["id"] for chunk in retrieved_chunks]

    # Answer
    draft = _answer_json(body.prompt, context_for_llm, contradictions)
    if not isinstance(draft, dict):
        raise HTTPException(status_code=500, detail="Answerer returned non-JSON")

    # Ensure citations are always a list of strings (ids only)
    if "citations" in draft and isinstance(draft["citations"], list):
        draft["citations"] = [
            c if isinstance(c, str) else c.get("id") for c in draft["citations"]
        ]

    # Red-team (non-fatal)
    try:
        verdict = review_answer(
            draft_json=draft,
            prompt=body.prompt,
            retrieved_chunks=retrieved_chunks
        ) or {}
    except Exception:
        verdict = {"action": "allow", "reasons": []}
    action = (verdict.get("action") or "allow").lower()

    if action == "block":
        return {
            "session_id": session_id,
            "answer": "I can’t answer confidently with the available evidence. Try adding filters or uploading the source.",
            "citations": [],
            "guidance_questions": ["Do you want me to search with a narrower tag or date range?"],
            "autosave": {"saved": False, "items": []},
            "redteam": verdict,
            "metrics": {"latency_ms": int((datetime.datetime.utcnow() - t0).total_seconds() * 1000)},
        }

    # -----------------------
    # Autosave (non-fatal) with robust fallback
    # -----------------------
    try:
        # Prefer LLM-provided autosave candidates
        candidates = (draft.get("autosave_candidates") or []).copy()

        # If none, derive from USER + ASSISTANT + small CONTEXT sample
        if not candidates:
            sample_ctx = "\n\n".join(
                [(c.get("text") or "")[:1200] for c in (retrieved_chunks[:2] if retrieved_chunks else [])]
            )
            fallback_text = (
                f"USER:\n{(body.prompt or '')[:4000]}\n\n"
                f"ASSISTANT:\n{(draft.get('answer') or '')[:4000]}\n\n"
                f"CONTEXT:\n{sample_ctx}"
            )
            derived = extract_signals_from_text(fallback_text) or []

            # Tag derived items with provenance + session for traceability
            for d in derived:
                tags = set(d.get("tags") or [])
                tags.update({"source:chat", f"session:{session_id}"})
                d["tags"] = sorted(list(tags))
            candidates.extend(derived)

        autosave = apply_autosave(
            sb=sb,
            pinecone_index=index,
            candidates=candidates,
            session_id=session_id,
            text_col_env=os.getenv("MEMORIES_TEXT_COLUMN", "text"),
            author_user_id=author_user_id,  # pass attribution
        )
    except Exception:
        autosave = {"saved": False, "items": []}

    # Persist messages (best-effort)
    message_id = None
    try:
        # Insert user message
        user_msg_result = sb.table("messages").insert(
            {"session_id": session_id, "role": "user", "content": body.prompt, "model": os.getenv("CHAT_MODEL")}
        ).execute()
        
        # Insert assistant message
        assistant_msg_result = sb.table("messages").insert(
            {
                "session_id": session_id,
                "role": "assistant",
                "content": draft.get("answer") or "",
                "model": os.getenv("CHAT_MODEL"),
                "latency_ms": int((datetime.datetime.utcnow() - t0).total_seconds() * 1000),
            }
        ).execute()
        
        # Get the assistant message ID for tracing
        if assistant_msg_result.data and len(assistant_msg_result.data) > 0:
            message_id = assistant_msg_result.data[0]["id"]
            
    except Exception as e:
        print(f"Failed to persist messages: {e}")
    
    # Log rheomode run if dual_index is enabled
    if get_feature_flag("retrieval.dual_index", default=False) and message_id and selection_result:
        try:
            total_time = (datetime.datetime.utcnow() - t0).total_seconds() * 1000
            timing = {
                "total_ms": total_time,
                "retrieval_ms": retrieval_time,
                "graph_expansion_ms": 0,  # Could be calculated if needed
                "llm_ms": total_time - retrieval_time
            }
            
            log_chat_request(
                session_id=session_id,
                message_id=message_id,
                role=body.role or "user",
                query=body.prompt,
                selection_result=selection_result,
                contradictions=contradictions,
                timing=timing,
                lift_score=lift_score,
                contradiction_score=contradiction_score
            )
        except Exception as e:
            print(f"Failed to log rheomode run: {e}")

    return {
        "session_id": session_id,
        "answer": draft.get("answer") or "",
        "citations": draft.get("citations") or [],
        "guidance_questions": draft.get("guidance_questions") or [],
        "autosave": autosave,
        "redteam": verdict,
        "metrics": {"latency_ms": int((datetime.datetime.utcnow() - t0).total_seconds() * 1000)},
    }
