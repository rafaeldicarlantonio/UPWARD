# External Citation Formatting

Formatting and presentation of external evidence sources in chat responses.

## Overview

External sources are rendered distinctly from internal sources with:
- Source labels (e.g., [Wikipedia], [arXiv])
- Normalized host domains
- Full provenance (URL, fetch timestamp)
- Truncated and redacted snippets
- Separate "External sources" section in responses

## Formatting Functions

### format_external_evidence()

Main function for formatting external evidence items.

```python
from core.presenters import format_external_evidence

external_items = [
    {
        "source_id": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/Machine_Learning",
        "snippet": "Machine learning is a subset of AI...",
        "fetched_at": "2025-10-30T12:00:00Z"
    }
]

result = format_external_evidence(external_items)
```

**Returns**:
```python
{
    "heading": "External sources",
    "items": [
        {
            "label": "Wikipedia",
            "host": "en.wikipedia.org",
            "snippet": "Machine learning is a subset...",
            "provenance": {
                "url": "https://en.wikipedia.org/wiki/Machine_Learning",
                "fetched_at": "2025-10-30T12:00:00Z"
            }
        }
    ]
}
```

### format_chat_response_with_externals()

Integrates external sources into chat responses.

```python
from core.presenters import format_chat_response_with_externals

response = {
    "answer": "Machine learning is...",
    "citations": []
}

enhanced_response = format_chat_response_with_externals(
    response,
    external_items=external_items
)

# Result includes:
# {
#     "answer": "...",
#     "citations": [],
#     "external_sources": {
#         "heading": "External sources",
#         "items": [...]
#     }
# }
```

## Formatting Features

### 1. Source Labels

Each item displays a human-readable label from the whitelist configuration:

| Source ID | Label |
|-----------|-------|
| `wikipedia` | Wikipedia |
| `arxiv` | arXiv |
| `pubmed` | PubMed |
| `scholar` | Google Scholar |

Unknown sources are title-cased from the ID: `my_source` → "My Source"

### 2. Normalized Host

Extracts clean domain from URL:

```python
"https://en.wikipedia.org/wiki/Page" → "en.wikipedia.org"
"https://arxiv.org/abs/1234.5678" → "arxiv.org"
"https://subdomain.example.com:8080/path" → "subdomain.example.com:8080"
```

### 3. Snippet Truncation

Snippets are truncated to `max_snippet_chars` from whitelist config:

- **Wikipedia**: 200 characters
- **arXiv**: 300 characters
- **Default**: 400 characters

Truncation respects word boundaries:

```python
# Original (300 chars)
"The quick brown fox jumps over the lazy dog..." * 10

# Truncated (200 chars max)
"The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox..."
```

### 4. Content Redaction

Applies redaction patterns from `compare_policy.yaml`:

**Default Patterns**:
- `Authorization: *` → `[REDACTED]`
- `Bearer <token>` → `[REDACTED]`
- Email addresses → `[REDACTED]`
- API keys → `[REDACTED]`

**Example**:
```python
# Before
"Contact support@example.com with Authorization: Bearer abc123"

# After
"Contact [REDACTED] with [REDACTED]"
```

### 5. Provenance Block

Each item includes full provenance:

```python
{
    "provenance": {
        "url": "https://en.wikipedia.org/wiki/Machine_Learning",
        "fetched_at": "2025-10-30T12:00:00Z"  # ISO 8601 timestamp
    }
}
```

## Response Structure

### Standard Chat Response

```json
{
    "answer": "Machine learning is a field of artificial intelligence...",
    "citations": [
        {
            "id": "mem_123",
            "text": "Internal source text...",
            "type": "memory"
        }
    ],
    "external_sources": {
        "heading": "External sources",
        "items": [
            {
                "label": "Wikipedia",
                "host": "en.wikipedia.org",
                "snippet": "Machine learning is a subset of AI...",
                "provenance": {
                    "url": "https://en.wikipedia.org/wiki/Machine_Learning",
                    "fetched_at": "2025-10-30T12:00:00Z"
                }
            },
            {
                "label": "arXiv",
                "host": "arxiv.org",
                "snippet": "This paper presents a novel approach...",
                "provenance": {
                    "url": "https://arxiv.org/abs/1234.5678",
                    "fetched_at": "2025-10-30T12:05:00Z"
                }
            }
        ]
    }
}
```

### Response Without External Sources

```json
{
    "answer": "...",
    "citations": [...],
    "external_sources": null
}
```

## UI Display Guidelines

### Recommended Rendering

```
Answer: Machine learning is a field of artificial intelligence...

Citations:
• Internal memory [mem_123]
• Internal document [doc_456]

External sources:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Wikipedia (en.wikipedia.org)
   Machine learning is a subset of AI that enables systems
   to learn and improve from experience...
   
   🔗 https://en.wikipedia.org/wiki/Machine_Learning
   📅 Fetched: 2025-10-30 12:00:00 UTC

📄 arXiv (arxiv.org)
   This paper presents a novel approach to deep learning
   architectures...
   
   🔗 https://arxiv.org/abs/1234.5678
   📅 Fetched: 2025-10-30 12:05:00 UTC
```

### React Component Example

```jsx
function ExternalSources({ externalSources }) {
  if (!externalSources || !externalSources.items?.length) {
    return null;
  }

  return (
    <div className="external-sources">
      <h3>{externalSources.heading}</h3>
      <div className="sources-list">
        {externalSources.items.map((item, idx) => (
          <div key={idx} className="source-item">
            <div className="source-header">
              <span className="label">{item.label}</span>
              <span className="host">({item.host})</span>
            </div>
            <p className="snippet">{item.snippet}</p>
            <div className="provenance">
              <a href={item.provenance.url} target="_blank">
                {item.provenance.url}
              </a>
              {item.provenance.fetched_at && (
                <span className="timestamp">
                  Fetched: {new Date(item.provenance.fetched_at).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Configuration

### Whitelist Configuration

In `config/external_sources_whitelist.json`:

```json
[
  {
    "source_id": "wikipedia",
    "label": "Wikipedia",
    "priority": 10,
    "url_pattern": "https://.*\\.wikipedia\\.org/.*",
    "max_snippet_chars": 200,
    "enabled": true
  }
]
```

Key fields for formatting:
- `label` - Display name
- `max_snippet_chars` - Truncation limit

### Policy Configuration

In `config/compare_policy.yaml`:

```yaml
redact_patterns:
  - "Authorization:\\s+\\S+"
  - "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*"
  - "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
  - "api[_-]?key['\"]?\\s*[:=]\\s*['\"]?[A-Za-z0-9]+"
```

## Testing

Comprehensive tests in `tests/external/test_citation_format.py`:

```bash
# Run all tests
pytest tests/external/test_citation_format.py -v

# Run specific test suite
pytest tests/external/test_citation_format.py::TestRedaction -v
```

### Test Coverage

- ✅ Basic formatting (4 tests)
- ✅ Truncation (4 tests)
- ✅ Redaction (4 tests)
- ✅ Provenance (3 tests)
- ✅ Host extraction (3 tests)
- ✅ Chat response integration (3 tests)
- ✅ Acceptance criteria (6 tests)
- ✅ Edge cases (4 tests)
- ✅ Comprehensive pipeline (1 test)

## Security Considerations

### Redaction Patterns

Always include patterns for:
- Authentication tokens
- API keys
- Email addresses
- Internal system IDs
- Personal identifiable information (PII)

### URL Validation

URLs are parsed safely using `urlparse()`. Invalid URLs fall back to "unknown" host.

### Content Sanitization

All snippets are:
1. Truncated to prevent excessive content
2. Redacted for sensitive information
3. Stripped of leading/trailing whitespace

## Troubleshooting

### Snippets Not Truncated

Check whitelist configuration:
```python
from core.config_loader import get_loader

loader = get_loader()
sources = loader.get_whitelist()
for source in sources:
    print(f"{source.source_id}: {source.max_snippet_chars} chars")
```

### Redaction Not Working

Check policy configuration:
```python
policy = loader.get_compare_policy()
print(f"Redaction patterns: {policy.redact_patterns}")
```

Test pattern matching:
```python
import re
text = "Authorization: Bearer token123"
pattern = r"Authorization:\s+\S+(\s+\S+)?"
result = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
print(result)  # Should be "[REDACTED]"
```

### Unknown Source Labels

If a source ID is not in the whitelist, it will be title-cased:
- `my_custom_source` → "My Custom Source"
- `arxiv` → "Arxiv"

Add to whitelist for proper labels.

## Related Documentation

- [External Sources Configuration](./external-sources-config.md)
- [Compare Policy](./compare-policy.md)
- [Chat Response Format](./chat-response-format.md)
- [Role-Based Redaction](./redaction-implementation.md)
