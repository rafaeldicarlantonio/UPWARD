# External Sources Configuration

Configuration system for managing external source whitelists and comparison policies with validation, safe defaults, and error handling.

## Overview

The configuration loader provides a robust system for:
- Managing whitelisted external sources (Wikipedia, arXiv, PubMed, etc.)
- Defining policies for external source comparison
- Validating configuration schemas
- Falling back to safe defaults on errors
- Runtime configuration reloading

## Configuration Files

### External Sources Whitelist

**Location**: `config/external_sources_whitelist.json`

**Format**: JSON array of source definitions

**Schema**:
```json
[
  {
    "source_id": "wikipedia",          // Required: Unique identifier
    "label": "Wikipedia",               // Required: Display name
    "priority": 10,                     // Required: Integer ≥ 0 (higher = preferred)
    "url_pattern": "https://.*\\.wikipedia\\.org/.*",  // Required: Regex pattern
    "max_snippet_chars": 480,          // Required: Integer > 0
    "enabled": true                     // Optional: Default true
  }
]
```

**Example**:
```json
[
  {
    "source_id": "wikipedia",
    "label": "Wikipedia",
    "priority": 10,
    "url_pattern": "https://.*\\.wikipedia\\.org/.*",
    "max_snippet_chars": 480,
    "enabled": true
  },
  {
    "source_id": "arxiv",
    "label": "arXiv",
    "priority": 9,
    "url_pattern": "https://arxiv\\.org/.*",
    "max_snippet_chars": 640,
    "enabled": true
  },
  {
    "source_id": "pubmed",
    "label": "PubMed",
    "priority": 8,
    "url_pattern": "https://pubmed\\.ncbi\\.nlm\\.nih\\.gov/.*",
    "max_snippet_chars": 500,
    "enabled": true
  }
]
```

**Validation Rules**:
- `source_id`: Must be non-empty string
- `priority`: Must be non-negative integer
- `url_pattern`: Must be valid regex
- `max_snippet_chars`: Must be positive integer
- `enabled`: Boolean (defaults to `true`)

**Behavior**:
- Sources are **sorted by priority** (highest first)
- Invalid entries are **skipped with warning**
- If all entries invalid, **defaults to Wikipedia only**

### Compare Policy

**Location**: `config/compare_policy.yaml`

**Format**: YAML mapping

**Schema**:
```yaml
# Maximum external sources to query per run
max_external_sources_per_run: 6          # Required: Integer ≥ 1

# Maximum total characters from all sources
max_total_external_chars: 2400           # Required: Integer ≥ 1

# Roles allowed to trigger external queries
allowed_roles_for_external:               # Required: List of strings
  - pro
  - scholars
  - analytics

# HTTP request timeout in milliseconds
timeout_ms_per_request: 2000             # Required: Integer ≥ 1

# Rate limit per domain
rate_limit_per_domain_per_min: 6         # Required: Integer ≥ 1

# Tie-breaking strategy
tie_break: prefer_internal                # Required: prefer_internal | prefer_external | abstain

# Regex patterns to redact from content
redact_patterns:                          # Optional: List of regex strings
  - "Authorization:\\s+\\S+"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
```

**Example**:
```yaml
max_external_sources_per_run: 6
max_total_external_chars: 2400
allowed_roles_for_external:
  - pro
  - scholars
  - analytics
timeout_ms_per_request: 2000
rate_limit_per_domain_per_min: 6
tie_break: prefer_internal
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
  - "api[_-]?key['\"]?\\s*[:=]\\s*['\"]?[A-Za-z0-9]+"
```

**Validation Rules**:
- All numeric fields must be positive integers
- `tie_break` must be one of: `prefer_internal`, `prefer_external`, `abstain`
- `redact_patterns` must be valid regex patterns
- Missing fields use **safe defaults**

## Usage

### Basic Usage

```python
from core.config_loader import get_loader

# Get global loader instance
loader = get_loader()

# Get enabled sources (sorted by priority)
sources = loader.get_whitelist()
for source in sources:
    print(f"{source.label}: priority {source.priority}")

# Get comparison policy
policy = loader.get_compare_policy()
print(f"Max sources: {policy.max_external_sources_per_run}")
print(f"Tie break: {policy.tie_break}")
```

### Advanced Usage

```python
from core.config_loader import ConfigLoader

# Custom paths
loader = ConfigLoader(
    whitelist_path="/path/to/whitelist.json",
    policy_path="/path/to/policy.yaml"
)

# Get all sources (including disabled)
all_sources = loader.get_whitelist(enabled_only=False)

# Get specific source by ID
wiki = loader.get_source_by_id("wikipedia")
if wiki:
    print(f"Wikipedia pattern: {wiki.url_pattern}")

# Export config as dict
config_dict = loader.to_dict()

# Reload from disk
loader.reload()
```

### Data Classes

```python
from core.config_loader import ExternalSource, ComparePolicy

# Create source programmatically
source = ExternalSource(
    source_id="custom",
    label="Custom Source",
    priority=5,
    url_pattern="https://example\\.com/.*",
    max_snippet_chars=400,
    enabled=True
)

# Create policy programmatically
policy = ComparePolicy(
    max_external_sources_per_run=3,
    max_total_external_chars=1200,
    allowed_roles_for_external=["pro"],
    timeout_ms_per_request=1000,
    rate_limit_per_domain_per_min=10,
    tie_break="prefer_external",
    redact_patterns=["secret:\\s+\\S+"]
)

# Convert to dict
source_dict = source.to_dict()
policy_dict = policy.to_dict()
```

## Default Configurations

### Default Whitelist

If the whitelist file is missing or all entries are invalid:

```python
[
    {
        "source_id": "wikipedia",
        "label": "Wikipedia",
        "priority": 10,
        "url_pattern": "https://.*\\.wikipedia\\.org/.*",
        "max_snippet_chars": 480,
        "enabled": True
    }
]
```

### Default Policy

If the policy file is missing or invalid:

```python
{
    "max_external_sources_per_run": 3,
    "max_total_external_chars": 1200,
    "allowed_roles_for_external": ["pro", "scholars", "analytics"],
    "timeout_ms_per_request": 2000,
    "rate_limit_per_domain_per_min": 6,
    "tie_break": "prefer_internal",
    "redact_patterns": [
        "Authorization:\\s+\\S+",
        "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
    ]
}
```

## Error Handling

The loader provides robust error handling:

### Missing Files

```python
# Missing whitelist
loader = ConfigLoader(whitelist_path="/nonexistent/file.json")
# WARNING: Whitelist file not found. Using default whitelist.
sources = loader.get_whitelist()  # Returns default Wikipedia source
```

### Invalid JSON/YAML

```python
# Malformed JSON
# ERROR: Failed to parse whitelist JSON: ... Using defaults.
sources = loader.get_whitelist()  # Returns defaults
```

### Invalid Entries

```python
# Entry missing required fields
# WARNING: Whitelist entry 0 missing required fields ['priority']. Skipping.

# Entry with invalid values
# WARNING: Invalid whitelist entry 1: priority must be non-negative. Skipping.
```

### Partial Overrides

Policy file with only some fields:

```yaml
# Only override these fields
max_external_sources_per_run: 10
tie_break: prefer_external
```

Result: Specified fields are overridden, others use defaults.

## Configuration Reloading

```python
loader = get_loader()

# ... application runs ...

# Reload configurations from disk
loader.reload()

# Or force recreation of global loader
loader = get_loader(force_reload=True)
```

## Validation Reference

### ExternalSource Validation

| Field | Type | Constraints | Default |
|-------|------|-------------|---------|
| `source_id` | string | Non-empty | Required |
| `label` | string | Any | Required |
| `priority` | integer | ≥ 0 | Required |
| `url_pattern` | string | Valid regex | Required |
| `max_snippet_chars` | integer | > 0 | Required |
| `enabled` | boolean | true/false | `true` |

### ComparePolicy Validation

| Field | Type | Constraints | Default |
|-------|------|-------------|---------|
| `max_external_sources_per_run` | integer | ≥ 1 | `3` |
| `max_total_external_chars` | integer | ≥ 1 | `1200` |
| `allowed_roles_for_external` | list | strings | `["pro", "scholars", "analytics"]` |
| `timeout_ms_per_request` | integer | ≥ 1 | `2000` |
| `rate_limit_per_domain_per_min` | integer | ≥ 1 | `6` |
| `tie_break` | string | `prefer_internal`, `prefer_external`, `abstain` | `prefer_internal` |
| `redact_patterns` | list | Valid regex strings | `[...]` |

## Testing

Comprehensive tests available in `tests/external/test_config_loader.py`:

```bash
# Run all tests
pytest tests/external/test_config_loader.py -v

# Run specific test suite
pytest tests/external/test_config_loader.py::TestConfigLoaderHappyPath -v

# Run with coverage
pytest tests/external/test_config_loader.py --cov=core.config_loader
```

**Test Coverage**:
- ✅ Valid configurations (happy path)
- ✅ Missing files (defaults)
- ✅ Malformed JSON/YAML
- ✅ Invalid field values
- ✅ Missing required fields
- ✅ Partial overrides
- ✅ Priority sorting
- ✅ Enabled/disabled filtering
- ✅ Configuration reloading
- ✅ Edge cases

## Best Practices

### Production Configuration

1. **Use explicit paths** for clarity:
```python
loader = ConfigLoader(
    whitelist_path="/etc/myapp/external_sources.json",
    policy_path="/etc/myapp/compare_policy.yaml"
)
```

2. **Monitor for warnings** in logs:
```python
import logging
logging.basicConfig(level=logging.WARNING)
```

3. **Validate configurations** in CI/CD:
```bash
pytest tests/external/test_config_loader.py
```

4. **Use version control** for config files

### Development Configuration

1. **Use workspace defaults**:
```python
loader = get_loader()  # Uses config/ directory
```

2. **Test error handling**:
```python
# Temporarily rename config file
# Verify application continues with defaults
```

3. **Document custom sources** in comments:
```json
{
  "source_id": "internal_wiki",
  "label": "Internal Wiki",
  "priority": 11,  // Higher than Wikipedia
  "url_pattern": "https://wiki\\.company\\.com/.*",
  "max_snippet_chars": 600,
  "enabled": true
}
```

## Security Considerations

### Redaction Patterns

Configure patterns to remove sensitive data:

```yaml
redact_patterns:
  # API keys
  - "api[_-]?key['\"]?\\s*[:=]\\s*['\"]?[A-Za-z0-9]+"
  
  # OAuth tokens
  - "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
  - "Authorization:\\s+\\S+"
  
  # Email addresses
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  
  # Credentials
  - "password['\"]?\\s*[:=]\\s*['\"]?[^'\"\\s]+"
```

### URL Patterns

Use **strict regex patterns** to prevent abuse:

```json
{
  "url_pattern": "https://en\\.wikipedia\\.org/wiki/[A-Za-z0-9_]+",
  "// AVOID": "https://.*"  // Too permissive
}
```

### Rate Limiting

Configure appropriate limits:

```yaml
rate_limit_per_domain_per_min: 6  # Conservative default
timeout_ms_per_request: 2000       # Prevent hanging
```

## Troubleshooting

### Configurations Not Loading

```python
import logging
logging.basicConfig(level=logging.DEBUG)

loader = get_loader()
# Check debug logs for file paths and errors
```

### Invalid Regex Patterns

```python
import re

pattern = "https://example\\.com/.*"
try:
    re.compile(pattern)
    print("Pattern valid")
except re.error as e:
    print(f"Invalid pattern: {e}")
```

### Sources Not Sorted

Verify priority values are integers:
```json
{
  "priority": 10,      // Correct
  "priority": "10"     // Wrong - will be skipped
}
```

## Related Documentation

- [External Sources Adapter](./external-sources-adapter.md)
- [Comparison Engine](./comparison-engine.md)
- [RBAC System](./rbac-system.md) - Role-based external access
