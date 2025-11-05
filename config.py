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
    
    # Factare configuration
    "FACTARE_ENABLED": False,
    "FACTARE_ALLOW_EXTERNAL": False,
    "FACTARE_EXTERNAL_TIMEOUT_MS": 2000,
    "FACTARE_MAX_SOURCES_INTERNAL": 24,
    "FACTARE_MAX_SOURCES_EXTERNAL": 8,
    "HYPOTHESES_PARETO_THRESHOLD": 0.65,

    # Ingest analysis configuration
    "INGEST_ANALYSIS_ENABLED": False,
    "INGEST_ANALYSIS_MAX_MS_PER_CHUNK": 40,
    "INGEST_ANALYSIS_MAX_VERBS": 20,
    "INGEST_ANALYSIS_MAX_FRAMES": 10,
    "INGEST_ANALYSIS_MAX_CONCEPTS": 10,
    "INGEST_CONTRADICTIONS_ENABLED": False,
    "INGEST_IMPLICATE_REFRESH_ENABLED": False,
    
    # Performance and fallback flags
    "PERF_RETRIEVAL_PARALLEL": True,
    "PERF_RETRIEVAL_TIMEOUT_MS": 450,
    "PERF_GRAPH_TIMEOUT_MS": 150,
    "PERF_COMPARE_TIMEOUT_MS": 400,
    "PERF_REVIEWER_ENABLED": True,
    "PERF_REVIEWER_BUDGET_MS": 500,
    "PERF_PGVECTOR_ENABLED": True,
    "PERF_FALLBACKS_ENABLED": True,
    
    # Resource limits and bulkheads
    "LIMITS_ENABLED": True,
    "LIMITS_MAX_CONCURRENT_PER_USER": 3,
    "LIMITS_MAX_QUEUE_SIZE_PER_USER": 10,
    "LIMITS_MAX_CONCURRENT_GLOBAL": 100,
    "LIMITS_MAX_QUEUE_SIZE_GLOBAL": 500,
    "LIMITS_RETRY_AFTER_SECONDS": 5,
    "LIMITS_QUEUE_TIMEOUT_SECONDS": 30.0,
    "LIMITS_OVERLOAD_POLICY": "drop_newest",  # drop_newest, drop_oldest, block
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
        elif k == "FACTARE_ENABLED":
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        elif k == "FACTARE_ALLOW_EXTERNAL":
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        elif k == "FACTARE_EXTERNAL_TIMEOUT_MS":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("FACTARE_EXTERNAL_TIMEOUT_MS must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"FACTARE_EXTERNAL_TIMEOUT_MS must be a non-negative integer, got: {val}")
        elif k == "FACTARE_MAX_SOURCES_INTERNAL":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("FACTARE_MAX_SOURCES_INTERNAL must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"FACTARE_MAX_SOURCES_INTERNAL must be a non-negative integer, got: {val}")
        elif k == "FACTARE_MAX_SOURCES_EXTERNAL":
            try:
                val = int(val)
                if val < 0:
                    raise ValueError("FACTARE_MAX_SOURCES_EXTERNAL must be non-negative")
            except (ValueError, TypeError):
                raise RuntimeError(f"FACTARE_MAX_SOURCES_EXTERNAL must be a non-negative integer, got: {val}")
        elif k == "HYPOTHESES_PARETO_THRESHOLD":
            try:
                val = float(val)
                if not 0.0 <= val <= 1.0:
                    raise ValueError("HYPOTHESES_PARETO_THRESHOLD must be between 0.0 and 1.0")
            except (ValueError, TypeError):
                raise RuntimeError(f"HYPOTHESES_PARETO_THRESHOLD must be a float between 0.0 and 1.0, got: {val}")
        elif k in {"INGEST_ANALYSIS_ENABLED", "INGEST_CONTRADICTIONS_ENABLED", "INGEST_IMPLICATE_REFRESH_ENABLED"}:
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        elif k in {
            "INGEST_ANALYSIS_MAX_MS_PER_CHUNK",
            "INGEST_ANALYSIS_MAX_VERBS",
            "INGEST_ANALYSIS_MAX_FRAMES",
            "INGEST_ANALYSIS_MAX_CONCEPTS",
        }:
            try:
                val = int(val)
                if val <= 0:
                    raise ValueError("value must be a positive integer")
            except (ValueError, TypeError):
                raise RuntimeError(
                    f"{k} must be a positive integer, got: {val}"
                )
        
        # Performance flags - boolean
        elif k in {
            "PERF_RETRIEVAL_PARALLEL",
            "PERF_REVIEWER_ENABLED",
            "PERF_PGVECTOR_ENABLED",
            "PERF_FALLBACKS_ENABLED",
        }:
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        
        # Performance flags - timeout budgets (must be positive integers)
        elif k in {
            "PERF_RETRIEVAL_TIMEOUT_MS",
            "PERF_GRAPH_TIMEOUT_MS",
            "PERF_COMPARE_TIMEOUT_MS",
            "PERF_REVIEWER_BUDGET_MS",
        }:
            try:
                val = int(val)
                if val <= 0:
                    raise ValueError(f"{k} must be a positive integer")
            except (ValueError, TypeError):
                raise RuntimeError(
                    f"{k} must be a positive integer, got: {val}"
                )
        
        # Resource limits - boolean flags
        elif k == "LIMITS_ENABLED":
            val = val.lower() in ('true', '1', 'yes', 'on') if isinstance(val, str) else bool(val)
        
        # Resource limits - positive integers
        elif k in {
            "LIMITS_MAX_CONCURRENT_PER_USER",
            "LIMITS_MAX_QUEUE_SIZE_PER_USER",
            "LIMITS_MAX_CONCURRENT_GLOBAL",
            "LIMITS_MAX_QUEUE_SIZE_GLOBAL",
            "LIMITS_RETRY_AFTER_SECONDS",
        }:
            try:
                val = int(val)
                if val <= 0:
                    raise ValueError(f"{k} must be a positive integer")
            except (ValueError, TypeError):
                raise RuntimeError(
                    f"{k} must be a positive integer, got: {val}"
                )
        
        # Resource limits - queue timeout (positive float)
        elif k == "LIMITS_QUEUE_TIMEOUT_SECONDS":
            try:
                val = float(val)
                if val <= 0:
                    raise ValueError("LIMITS_QUEUE_TIMEOUT_SECONDS must be positive")
            except (ValueError, TypeError):
                raise RuntimeError(
                    f"LIMITS_QUEUE_TIMEOUT_SECONDS must be a positive float, got: {val}"
                )
        
        # Resource limits - overload policy
        elif k == "LIMITS_OVERLOAD_POLICY":
            valid_policies = ["drop_newest", "drop_oldest", "block"]
            if val not in valid_policies:
                raise RuntimeError(
                    f"LIMITS_OVERLOAD_POLICY must be one of {valid_policies}, got: {val}"
                )
        
        cfg[k] = val

    return cfg

# Misc operational tuning. Keep these here so you don’t hardcode magic numbers elsewhere.
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
TOPK_PER_TYPE = int(os.getenv("TOPK_PER_TYPE", "30"))
RECENCY_HALFLIFE_DAYS = int(os.getenv("RECENCY_HALFLIFE_DAYS", "90"))
RECENCY_FLOOR = float(os.getenv("RECENCY_FLOOR", "0.35"))


def get_debug_config():
    """
    Get configuration for debug endpoint.
    Returns sanitized config (no secrets) with performance flags.
    """
    from typing import Dict, Any
    import time
    
    cfg = load_config()
    
    # Remove sensitive keys
    sanitized = {
        k: v for k, v in cfg.items()
        if not any(secret in k.upper() for secret in ["KEY", "SECRET", "PASSWORD", "TOKEN"])
    }
    
    # Add metadata
    sanitized["_metadata"] = {
        "version": "1.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "loaded_at": time.time()
    }
    
    return sanitized


def validate_perf_config(cfg):
    """
    Validate performance configuration.
    
    Returns:
        Dict of validation errors (empty if all valid)
    """
    from typing import Dict
    
    errors = {}
    
    # Validate timeout budgets are reasonable
    if cfg.get("PERF_RETRIEVAL_TIMEOUT_MS", 0) > 1000:
        errors["PERF_RETRIEVAL_TIMEOUT_MS"] = "Should be ≤ 1000ms for responsive UX"
    
    if cfg.get("PERF_GRAPH_TIMEOUT_MS", 0) > 300:
        errors["PERF_GRAPH_TIMEOUT_MS"] = "Should be ≤ 300ms to avoid blocking retrieval"
    
    if cfg.get("PERF_COMPARE_TIMEOUT_MS", 0) > 1000:
        errors["PERF_COMPARE_TIMEOUT_MS"] = "Should be ≤ 1000ms for internal comparisons"
    
    if cfg.get("PERF_REVIEWER_BUDGET_MS", 0) > 1000:
        errors["PERF_REVIEWER_BUDGET_MS"] = "Should be ≤ 1000ms for answer review"
    
    # Validate parallel retrieval doesn't conflict with pgvector
    if cfg.get("PERF_RETRIEVAL_PARALLEL") and not cfg.get("PERF_PGVECTOR_ENABLED"):
        errors["PERF_RETRIEVAL_PARALLEL"] = "Parallel retrieval requires pgvector to be enabled"
    
    return errors
