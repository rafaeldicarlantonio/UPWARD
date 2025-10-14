#!/bin/bash
# scripts/backfill_implicate.sh — CLI script for building implicate index

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MODE="full"
MIN_DEGREE=5
BATCH_SIZE=50
ENTITY_IDS=""

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build implicate index from entities, entity_edges, and memories.

OPTIONS:
    -m, --mode MODE           Build mode: 'full' or 'incremental' (default: full)
    -d, --min-degree N        Minimum in-degree for entities in full mode (default: 5)
    -b, --batch-size N        Batch size for processing (default: 50)
    -e, --entity-ids IDS      Comma-separated entity IDs for incremental mode
    -h, --help                Show this help message

EXAMPLES:
    # Full build with default settings
    $0

    # Full build with custom minimum degree
    $0 --mode full --min-degree 10

    # Incremental build for specific entities
    $0 --mode incremental --entity-ids "uuid1,uuid2,uuid3"

    # Custom batch size
    $0 --batch-size 100

ENVIRONMENT VARIABLES:
    OPENAI_API_KEY            OpenAI API key (required)
    SUPABASE_URL              Supabase URL (required)
    SUPABASE_SERVICE_ROLE_KEY Supabase service role key (required)
    PINECONE_API_KEY          Pinecone API key (required)
    PINECONE_IMPLICATE_INDEX  Pinecone implicate index name (required)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -d|--min-degree)
            MIN_DEGREE="$2"
            shift 2
            ;;
        -b|--batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        -e|--entity-ids)
            ENTITY_IDS="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate mode
if [[ "$MODE" != "full" && "$MODE" != "incremental" ]]; then
    print_error "Invalid mode: $MODE. Must be 'full' or 'incremental'"
    exit 1
fi

# Validate incremental mode requirements
if [[ "$MODE" == "incremental" && -z "$ENTITY_IDS" ]]; then
    print_error "Entity IDs required for incremental mode. Use --entity-ids option."
    exit 1
fi

# Check required environment variables
print_status "Checking environment variables..."

required_vars=(
    "OPENAI_API_KEY"
    "SUPABASE_URL" 
    "SUPABASE_SERVICE_ROLE_KEY"
    "PINECONE_API_KEY"
    "PINECONE_IMPLICATE_INDEX"
)

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
    echo ""
    echo "Please set these variables and try again."
    exit 1
fi

print_success "All required environment variables are set"

# Check if we're in the right directory
if [[ ! -f "jobs/implicate_builder.py" ]]; then
    print_error "implicate_builder.py not found. Please run this script from the project root."
    exit 1
fi

# Print configuration
print_status "Configuration:"
echo "  Mode: $MODE"
echo "  Min Degree: $MIN_DEGREE"
echo "  Batch Size: $BATCH_SIZE"
if [[ "$MODE" == "incremental" ]]; then
    echo "  Entity IDs: $ENTITY_IDS"
fi
echo ""

# Build the command
PYTHON_CMD="python3 jobs/implicate_builder.py --mode $MODE --min-degree $MIN_DEGREE --batch-size $BATCH_SIZE"

if [[ "$MODE" == "incremental" ]]; then
    # Convert comma-separated IDs to space-separated for the script
    entity_ids_array=($(echo "$ENTITY_IDS" | tr ',' ' '))
    PYTHON_CMD="$PYTHON_CMD --entity-ids ${entity_ids_array[*]}"
fi

# Run the implicate builder
print_status "Starting implicate index build..."
echo "Command: PYTHONPATH=/workspace $PYTHON_CMD"
echo ""

# Capture the start time
start_time=$(date +%s)

# Run the command and capture output
if PYTHONPATH=/workspace eval "$PYTHON_CMD"; then
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    print_success "Implicate index build completed successfully!"
    print_status "Total duration: ${duration} seconds"
    
    # Show final stats if possible
    print_status "Getting final statistics..."
    PYTHONPATH=/workspace python3 -c "
from jobs.implicate_builder import ImplicateBuilder
try:
    builder = ImplicateBuilder()
    stats = builder.get_build_stats()
    print(f'Database entities: {stats[\"database\"][\"entity_counts\"]}')
    print(f'Total edges: {stats[\"database\"][\"total_edges\"]}')
    print(f'Total memories: {stats[\"database\"][\"total_memories\"]}')
    if stats['pinecone'].get('success', True):
        print(f'Pinecone vectors: {stats[\"pinecone\"].get(\"total_vector_count\", \"unknown\")}')
    else:
        print('Pinecone stats: unavailable')
except Exception as e:
    print(f'Could not get final stats: {e}')
"
    
    exit 0
else
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    print_error "Implicate index build failed!"
    print_status "Duration before failure: ${duration} seconds"
    exit 1
fi