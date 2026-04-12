# OWUI Retrieval API — Reference

Quick reference for the OWUI API endpoints used by the deep research pipeline. Based on Open WebUI's REST API.

## Knowledge Collections

### List All Collections

```
GET /api/v1/knowledge/
Authorization: Bearer {api_key}
```

Response:

```json
[
  {
    "id": "uuid",
    "name": "Unreal Engine 5.4 Docs",
    "description": "Official UE5.4 documentation",
    "data": {
      "file_ids": ["file-uuid-1", "file-uuid-2"]
    },
    "created_at": 1234567890,
    "updated_at": 1234567890
  }
]
```

### Get Collection by ID

```
GET /api/v1/knowledge/{id}
Authorization: Bearer {api_key}
```

Returns full collection metadata including file list.

## RAG Retrieval

### Query a Collection

```
POST /api/v1/retrieval/query
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "collection_name": "{collection_id}",
  "query": "your search query",
  "k": 5,
  "r": 0.0
}
```

Parameters:

- `collection_name` — the collection ID (UUID) to search
- `query` — natural language query string
- `k` — number of top results to return (top-K)
- `r` — relevance score threshold (0.0 = no filter)

Response:

```json
{
  "documents": [["chunk text 1", "chunk text 2"]],
  "metadatas": [[{ "source": "file.md", "page": 1 }]],
  "distances": [[0.23, 0.45]]
}
```

## Usage in Deep Research Pipeline

### Collection Discovery Flow

```python
# 1. List all collections
collections = httpx.get(
    f"{base_url}/api/v1/knowledge/",
    headers={"Authorization": f"Bearer {api_key}"}
).json()

# 2. Build summary for LLM ranking
summaries = [
    f"- {c['name']}: {c.get('description', 'No description')} "
    f"({len(c.get('data', {}).get('file_ids', []))} files)"
    for c in collections
]

# 3. LLM selects relevant collections (sub-agent call)
# 4. Query selected collections with initial + expanded terms
```

### Iterative Query Pattern

```python
seen_chunks: set[tuple[str, str]] = set()  # (collection_id, chunk_hash)

for iteration in range(max_iterations):
    for term in search_terms:
        for collection_id in selected_collections:
            result = httpx.post(
                f"{base_url}/api/v1/retrieval/query",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "collection_name": collection_id,
                    "query": term,
                    "k": top_k,
                }
            ).json()

            for chunk in result["documents"][0]:
                chunk_key = (collection_id, hashlib.sha256(chunk.encode()).hexdigest()[:16])
                if chunk_key not in seen_chunks:
                    seen_chunks.add(chunk_key)
                    new_chunks.append(chunk)
```

## Rate Limiting Considerations

OWUI's API is typically self-hosted with no rate limits, but the pipeline should:

- Batch queries where possible (one query per collection per term, not per chunk)
- Use `httpx.AsyncClient` with connection pooling
- Respect the `max_collections` valve to avoid querying dozens of collections
