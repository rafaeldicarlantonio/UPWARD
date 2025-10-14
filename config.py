# config.py — sane config with loud failures

import os

# Hard requirements. Fail fast if any are missing.
REQUIRED = [
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
    "PINECONE_EXPLICATE_INDEX",
    "PINECONE_IMPLICATE_INDEX",
]

# Optional knobs with defaults that won't sandbag you at runtime.
DEFAULTS = {
    "EMBED_MODEL": "text-embedding-3-small",
    "MEMORIES_TEXT_COLUMN": "text",
    "EMBED_DIM": None,   # None = let model decide / must match index
    "X_API_KEY": None,   # optional request auth for your endpoints
    
    # REDO/ledger configuration
    "ORCHESTRATOR_REDO_ENABLED": False,
    "LEDGER_ENABLED": False,
    "LEDGER_LEVEL": "off",  # off, min, full
    "LEDGER_MAX_TRACE_BYTES": 100_000,
    "LEDGER_SUMMARY_MAX_LINES": 4,
    "ORCHESTRATION_TIME_BUDGET_MS": 400,
}

def load_config():
    """
    Load env config, erroring clearly if anything critical is missing.
    Returns a dict of required + defaults (with types normalized).
    """
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        missing_list = ', '.join(missing)
        raise RuntimeError(
            f"Missing required environment variables: {missing_list}. "
            f"Please check your .env file and ensure all required variables are set. "
            f"See env.sample for reference."
        )

    cfg = {k: os.getenv(k) for k in REQUIRED}

    # Validate Pinecone indices are different
    if cfg.get("PINECONE_INDEX") == cfg.get("PINECONE_EXPLICATE_INDEX"):
        raise RuntimeError(
            "PINECONE_INDEX and PINECONE_EXPLICATE_INDEX must be different indices"
        )
    if cfg.get("PINECONE_INDEX") == cfg.get("PINECONE_IMPLICATE_INDEX"):
        raise RuntimeError(
            "PINECONE_INDEX and PINECONE_IMPLICATE_INDEX must be different indices"
        )
    if cfg.get("PINECONE_EXPLICATE_INDEX") == cfg.get("PINECONE_IMPLICATE_INDEX"):
        raise RuntimeError(
            "PINECONE_EXPLICATE_INDEX and PINECONE_IMPLICATE_INDEX must be different indices"
        )

    for k, v in DEFAULTS.items():
        val = os.getenv(k, v)
        
        # Type conversion and validation
        if k == "EMBED_DIM" and val is not None and val != "":
            try:
                val = int(val)
            except Exception:
                raise RuntimeError("EMBED_DIM must be an integer if provided")
        elif k == "ORCHESTRATOR_REDO_ENABLED":
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        elif k == "LEDGER_ENABLED":
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        elif k == "LEDGER_LEVEL":
            if val not in ['off', 'min', 'full']:
                raise RuntimeError(f"LEDGER_LEVEL must be one of 'off', 'min', 'full', got: {val}")
        elif k == "LEDGER_MAX_TRACE_BYTES":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("LEDGER_MAX_TRACE_BYTES must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"LEDGER_MAX_TRACE_BYTES must be a non-negative integer, got: {val}")
        elif k == "LEDGER_SUMMARY_MAX_LINES":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("LEDGER_SUMMARY_MAX_LINES must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"LEDGER_SUMMARY_MAX_LINES must be a non-negative integer, got: {val}")
        elif k == "ORCHESTRATION_TIME_BUDGET_MS":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("ORCHESTRATION_TIME_BUDGET_MS must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"ORCHESTRATION_TIME_BUDGET_MS must be a non-negative integer, got: {val}")
        
        cfg[k] = val

    return cfg

# Misc operational tuning. Keep these here so you don’t hardcode magic numbers elsewhere.
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
TOPK_PER_TYPE = int(os.getenv("TOPK_PER_TYPE", "30"))
RECENCY_HALFLIFE_DAYS = int(os.getenv("RECENCY_HALFLIFE_DAYS", "90"))
RECENCY_FLOOR = float(os.getenv("RECENCY_FLOOR", "0.35"))
