# Render Deployment Guide

## Issue Fixed ✅

**Problem**: `ERROR: Attribute "app" not found in module "app"`

**Root Cause**: Python naming conflict between `app.py` file and `app/` directory. Python imports the directory instead of the file.

**Solution**: Renamed `app.py` → `main.py` and updated start command to `uvicorn main:app`

---

## Deployment Steps

### 1. Required Environment Variables

Set these in Render Dashboard → Environment tab:

```
✅ OPENAI_API_KEY              (your OpenAI API key)
✅ SUPABASE_URL                (your Supabase project URL)
✅ PINECONE_API_KEY            (your Pinecone API key)
✅ PINECONE_INDEX              (your Pinecone index name)
✅ PINECONE_EXPLICATE_INDEX    (explicate index name)
✅ PINECONE_IMPLICATE_INDEX    (implicate index name)
```

**If you only have ONE Pinecone index**, use the same name for all three:
```
PINECONE_INDEX=memories
PINECONE_EXPLICATE_INDEX=memories
PINECONE_IMPLICATE_INDEX=memories
```

### 2. Verify Start Command

Render should automatically read from `render.yaml`:
```yaml
startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
```

Or manually set in Render Dashboard → Settings → Start Command:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 3. Deploy

```bash
git add main.py render.yaml RENDER_DEPLOYMENT.md
git commit -m "fix: Rename app.py to main.py to resolve import conflict"
git push
```

Render will auto-deploy.

### 4. Verify Deployment

Once deployed, test these endpoints:

```bash
# Health check
curl https://your-app.onrender.com/healthz

# Should return:
# {"status":"ok"}

# If config failed, you'll see:
# {"status":"degraded","error":"configuration_failed","message":"..."}

# Root endpoint
curl https://your-app.onrender.com/

# Debug endpoints
curl https://your-app.onrender.com/debug/routers
curl https://your-app.onrender.com/debug/config
```

---

## Troubleshooting

### Still seeing "app not found"?

1. **Check file was renamed**: Ensure `app.py` is renamed to `main.py`
2. **Check start command**: Must be `uvicorn main:app` (not `app:app`)
3. **Clear build cache**: In Render, Manual Deploy → "Clear build cache & deploy"

### Configuration errors after deployment?

Visit your app URL and check the root endpoint:
```bash
curl https://your-app.onrender.com/
```

If you see `"status": "error"`, the response will tell you exactly which environment variables are missing.

### Test locally before deploying

```bash
# Run the diagnostic script
python test_render_config.py

# Start server locally
uvicorn main:app --reload
```

---

## Files Changed

- `app.py` → `main.py` (renamed)
- `render.yaml` (updated startCommand)
- `test_render_config.py` (updated to use main.py)

---

## What Happened

1. **Original problem**: `app.py` file + `app/` directory caused import conflict
2. **Python behavior**: Directories take precedence over .py files in imports
3. **Uvicorn command**: `uvicorn app:app` tried to import from `app/` directory
4. **Result**: Module imported but had no `app` attribute (it's a React app directory)
5. **Fix**: Renamed to `main.py` to avoid conflict

---

## Next Steps After Successful Deploy

1. Test all endpoints
2. Check metrics: `curl https://your-app.onrender.com/debug/metrics`
3. Run smoke test: `python tools/load_smoke.py --url https://your-app.onrender.com`
4. Set up monitoring alerts
5. Review logs for any warnings

---

**Last Updated**: 2025-11-04
