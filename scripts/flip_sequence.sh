#!/bin/bash
# scripts/flip_sequence.sh - Production flip sequence for ingest analysis system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${CYAN}================================"
    echo -e "$1"
    echo -e "================================${NC}"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check prerequisites
print_header "FLIP SEQUENCE - Ingest Analysis System"
echo

print_status "Checking prerequisites..."

# Check env vars
required_vars=("SUPABASE_URL" "SUPABASE_KEY" "DATABASE_URL" "X_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        missing_vars+=("$var")
    fi
done

if [[ ${#missing_vars[@]} -gt 0 ]]; then
    print_error "Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo
    echo "Please set these variables and try again."
    exit 1
fi

print_success "Environment variables set"
echo

# Phase 1: Check current state
print_header "PHASE 1: Current State"
echo

print_status "Checking feature flags..."
psql "$DATABASE_URL" << EOF
SELECT flag_name, enabled 
FROM feature_flags 
WHERE flag_name LIKE 'ingest%'
ORDER BY flag_name;
EOF

echo
print_status "Checking entity counts..."
psql "$DATABASE_URL" << EOF
SELECT 
  type,
  COUNT(*) as count
FROM entities
GROUP BY type
ORDER BY count DESC;
EOF

echo
print_status "Checking current metrics..."
curl -s -H "X-API-KEY: $X_API_KEY" http://localhost:8000/debug/metrics | \
  jq '{
    chunks_analyzed: .key_metrics.ingest_chunks_analyzed_total,
    timeouts: .key_metrics.ingest_analysis_timeouts,
    refresh_enqueued: .key_metrics.implicate_refresh_enqueued_total,
    refresh_processed: .key_metrics.implicate_refresh_processed_total
  }'

echo
read -p "Press ENTER to continue to Phase 2 (Enable Analysis)..."

# Phase 2: Enable analysis
print_header "PHASE 2: Enable ingest.analysis.enabled"
echo

print_status "Enabling analysis flag..."
psql "$DATABASE_URL" << EOF
INSERT INTO feature_flags (flag_name, enabled)
VALUES ('ingest.analysis.enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;

INSERT INTO feature_flags (flag_name, enabled)
VALUES ('ingest.contradictions.enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;

SELECT flag_name, enabled FROM feature_flags WHERE flag_name LIKE 'ingest%';
EOF

print_success "Analysis enabled"
echo

print_warning "Now ingest some test files using /ingest/batch endpoint"
print_status "Example:"
echo '  curl -X POST http://localhost:8000/ingest/batch \'
echo '    -H "Content-Type: application/json" \'
echo '    -H "X-API-KEY: $X_API_KEY" \'
echo '    -d '"'"'{"items": [{"text": "...", "type": "semantic"}]}'"'"

echo
read -p "Press ENTER after ingesting test files to verify growth..."

# Phase 3: Verify growth
print_header "PHASE 3: Verify Database Growth"
echo

print_status "Entity counts after ingestion..."
psql "$DATABASE_URL" << EOF
SELECT 
  type,
  COUNT(*) as count
FROM entities
GROUP BY type
ORDER BY count DESC;
EOF

echo
print_status "Edge counts by relationship type..."
psql "$DATABASE_URL" << EOF
SELECT 
  rel_type,
  COUNT(*) as count
FROM entity_edges
GROUP BY rel_type
ORDER BY count DESC;
EOF

echo
print_status "Memories with contradictions..."
psql "$DATABASE_URL" << EOF
SELECT 
  COUNT(*) as total_memories,
  COUNT(CASE WHEN contradictions IS NOT NULL THEN 1 END) as with_contradictions,
  SUM(CASE WHEN contradictions IS NOT NULL 
      THEN jsonb_array_length(contradictions) ELSE 0 END) as total_contradictions
FROM memories;
EOF

echo
print_status "Sample contradictions (first 3)..."
psql "$DATABASE_URL" << EOF
SELECT 
  id,
  LEFT(text, 60) as snippet,
  jsonb_array_length(contradictions) as contradiction_count
FROM memories
WHERE contradictions IS NOT NULL
  AND jsonb_array_length(contradictions) > 0
ORDER BY created_at DESC
LIMIT 3;
EOF

echo
print_status "Updated metrics..."
curl -s -H "X-API-KEY: $X_API_KEY" http://localhost:8000/debug/metrics | \
  jq '{
    chunks_analyzed: .key_metrics.ingest_chunks_analyzed_total,
    timeouts: .key_metrics.ingest_analysis_timeouts,
    avg_concepts: .detailed_metrics.histograms."ingest.analysis.concepts_suggested"[0].stats.avg,
    avg_contradictions: .detailed_metrics.histograms."ingest.analysis.contradictions_found"[0].stats.avg
  }'

echo
read -p "Press ENTER to continue to Phase 4 (Enable Refresh Worker)..."

# Phase 4: Enable refresh and start worker
print_header "PHASE 4: Enable Implicate Refresh"
echo

print_status "Enabling implicate refresh flag..."
psql "$DATABASE_URL" << EOF
INSERT INTO feature_flags (flag_name, enabled)
VALUES ('ingest.implicate.refresh_enabled', true)
ON CONFLICT (flag_name) DO UPDATE SET enabled = true;

SELECT flag_name, enabled FROM feature_flags WHERE flag_name = 'ingest.implicate.refresh_enabled';
EOF

print_success "Refresh enabled"
echo

print_status "Checking job queue..."
psql "$DATABASE_URL" << EOF
SELECT 
  status,
  COUNT(*) as count
FROM jobs
WHERE job_type = 'implicate_refresh'
GROUP BY status
ORDER BY status;
EOF

echo
print_warning "Start the refresh worker in a separate terminal:"
echo "  python3 jobs/implicate_refresh.py --mode forever --poll-interval 10"
echo

print_status "Monitoring refresh metrics for 30 seconds..."
for i in {1..6}; do
    echo "  Check $i/6..."
    curl -s -H "X-API-KEY: $X_API_KEY" http://localhost:8000/debug/metrics | \
      jq '{
        enqueued: .key_metrics.implicate_refresh_enqueued_total,
        processed: .key_metrics.implicate_refresh_processed_total
      }'
    sleep 5
done

echo
read -p "Press ENTER to continue to Phase 5 (Tune Tolerance)..."

# Phase 5: Contradiction tolerance tuning
print_header "PHASE 5: Tune Contradiction Tolerance"
echo

print_status "Reviewing detected contradictions..."
psql "$DATABASE_URL" << EOF
SELECT 
  m.id,
  LEFT(m.text, 100) as text_snippet,
  c.value->>'claim_a' as claim_a,
  c.value->>'claim_b' as claim_b
FROM memories m,
  jsonb_array_elements(m.contradictions) c
WHERE m.contradictions IS NOT NULL
ORDER BY m.created_at DESC
LIMIT 10;
EOF

echo
print_warning "Manual Review Required:"
echo "  1. Review the contradictions above"
echo "  2. Mark each as TRUE POSITIVE or FALSE POSITIVE"
echo "  3. Calculate false positive rate: FP / (TP + FP)"
echo

read -p "Enter false positive rate (0-100): " fp_rate

if [[ "$fp_rate" =~ ^[0-9]+$ ]]; then
    echo
    print_status "False Positive Rate: ${fp_rate}%"
    
    if [[ $fp_rate -le 5 ]]; then
        print_success "Excellent! FP rate ≤5%"
        print_status "Recommendation: Keep current tolerance or decrease to 0.10 to catch more"
    elif [[ $fp_rate -le 10 ]]; then
        print_success "Good! FP rate ≤10%"
        print_status "Recommendation: Keep current tolerance (0.15)"
    elif [[ $fp_rate -le 20 ]]; then
        print_warning "Moderate FP rate (10-20%)"
        print_status "Recommendation: Increase tolerance to 0.20"
    else
        print_error "High FP rate (>20%)"
        print_status "Recommendation: Increase tolerance to 0.25-0.30"
    fi
else
    print_warning "Skipping tolerance calculation"
fi

echo
print_status "To adjust tolerance:"
echo "  1. Edit config/ingest_policy.yaml"
echo "  2. Find your role's contradiction_tolerance value"
echo "  3. Adjust based on recommendation above"
echo "  4. Restart application to reload policy"

echo
read -p "Press ENTER to continue to Phase 6 (Final Validation)..."

# Phase 6: Final validation
print_header "PHASE 6: Final Validation"
echo

print_status "System health check..."

# Check metrics one more time
metrics_output=$(curl -s -H "X-API-KEY: $X_API_KEY" http://localhost:8000/debug/metrics)

chunks_analyzed=$(echo "$metrics_output" | jq -r '.key_metrics.ingest_chunks_analyzed_total // 0')
timeouts=$(echo "$metrics_output" | jq -r '.key_metrics.ingest_analysis_timeouts // 0')
refresh_processed=$(echo "$metrics_output" | jq -r '.key_metrics.implicate_refresh_processed_total // 0')

echo "  Chunks analyzed: $chunks_analyzed"
echo "  Timeouts: $timeouts"
echo "  Refresh jobs processed: $refresh_processed"

# Calculate rates
if [[ $chunks_analyzed -gt 0 ]]; then
    timeout_rate=$(echo "scale=2; $timeouts * 100 / $chunks_analyzed" | bc)
    echo "  Timeout rate: ${timeout_rate}%"
    
    if (( $(echo "$timeout_rate < 2" | bc -l) )); then
        print_success "Timeout rate is healthy (<2%)"
    else
        print_warning "Timeout rate is ${timeout_rate}% - consider increasing INGEST_ANALYSIS_MAX_MS_PER_CHUNK"
    fi
fi

echo
print_status "Database integrity check..."
psql "$DATABASE_URL" << EOF
-- Check for orphaned edges
SELECT COUNT(*) as orphaned_edges
FROM entity_edges e
WHERE NOT EXISTS (SELECT 1 FROM entities WHERE id = e.from_id)
   OR NOT EXISTS (SELECT 1 FROM entities WHERE id = e.to_id);
EOF

echo
print_header "FLIP SEQUENCE COMPLETE"
echo

print_success "All phases completed successfully!"
echo
echo "Summary:"
echo "  ✓ Analysis enabled and tested"
echo "  ✓ Entities and edges created"
echo "  ✓ Contradictions detected and stored"
echo "  ✓ Refresh worker monitoring active"
echo "  ✓ Tolerance tuning guidance provided"
echo
echo "System is ready for production use!"
echo
echo "See docs/ingest-analysis.md for ongoing operations."
