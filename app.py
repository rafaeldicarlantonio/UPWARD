# app.py — mounts routers, exposes health, and surfaces mount failures

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load config once at startup. Fail loudly if env is broken.
from config import (
    load_config,
    MAX_CONTEXT_TOKENS,
    TOPK_PER_TYPE,
    RECENCY_HALFLIFE_DAYS,
    RECENCY_FLOOR,
)

try:
    CFG = load_config()
except Exception as e:
    import sys
    import traceback
    print("=" * 80, file=sys.stderr)
    print("FATAL: Failed to load configuration", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Error: {e}", file=sys.stderr)
    print(file=sys.stderr)
    print("Full traceback:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("Check your environment variables in Render dashboard", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    sys.exit(1)

app = FastAPI(
    title="SUAPS Brain",
    version="0.1.0",
    description="RAG-ish brain that now actually tells you when things are broken."
)

# CORS — permissive for now; lock down later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track router mount failures so 404s aren’t mysteries.
_router_failures = []
_mounted = []

def _mount(router_module_name: str):
    try:
        mod = __import__(f"router.{router_module_name}", fromlist=["router"])
        app.include_router(mod.router)
        _mounted.append(router_module_name)
        print(f"[routers] mounted /{router_module_name}")
    except Exception as e:
        msg = repr(e)
        _router_failures.append({"router": router_module_name, "error": msg})
        print(f"[routers] WARNING: failed to mount '{router_module_name}': {msg}")

# Mount all known routers. If any explode at import-time, we’ll see it in /debug/routers.
_mount("chat")
_mount("upload")
_mount("ingest")
_mount("memories")
_mount("search")
_mount("entities")

@app.get("/debug/routers")
def debug_routers():
    """
    Shows which routers mounted successfully and which face-planted at import time.
    Use this the next time /search returns 404 and you swear it exists.
    """
    return {
        "mounted": _mounted,
        "failures": _router_failures,
    }

@app.get("/healthz")
async def healthz():
    """Minimal liveness probe."""
    return {"status": "ok"}


@app.get("/debug/selftest")
async def debug_selftest():
    """
    Best-effort checks. All failures are non-fatal.
    - DB connect if DATABASE_URL is set
    - Pinecone flagged false for now
    Returns: { db_ok, pinecone_ok, counts: {}, timings: {}, errors: {..} }
    """
    out = {"db_ok": False, "pinecone_ok": False, "counts": {}, "timings": {}, "errors": {}}

    # Database connectivity (optional)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        import time
        t0 = time.time()
        try:
            import asyncpg  # type: ignore
            conn = await asyncpg.connect(db_url, timeout=5)
            try:
                out["db_ok"] = True
            finally:
                await conn.close()
            out["timings"]["db_ms"] = int((time.time() - t0) * 1000)
        except Exception as e:
            out["db_ok"] = False
            out["errors"]["db"] = str(e)
    else:
        out["errors"]["db"] = "DATABASE_URL not set"

    # Pinecone: not checked here
    out["pinecone_ok"] = False  # false_for_now

    return out
