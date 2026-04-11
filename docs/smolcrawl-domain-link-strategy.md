# SmolCrawl Domain Link Strategy

SmolCrawl is designed to be a domain-constrained web crawler. This document outlines the technical strategy used to ensure the crawler stays within the boundaries of the target domain.

## Summary
SmolCrawl strictly follows links that share the same `netloc` (domain name and port) as the initial seed URL. It ignores all external links, including those to subdomains.

## Implementation Details

### 1. Domain Validation
The core of the logic resides in the `is_same_domain` function within `src/smolcrawl/crawl.py`. This function uses Python's `urllib.parse.urlparse` to extract the `netloc` and performs a direct equality check.

```python
def is_same_domain(url: str, base_url: str) -> bool:
    """Check if URL belongs to the same domain as the base URL."""
    try:
        url_parsed = urlparse(url)
        base_parsed = urlparse(base_url)
        return url_parsed.netloc == base_parsed.netloc
    except Exception:
        return False
```

### 2. Extraction Filtering
During the link extraction process, every anchor tag discovered in the HTML is processed:
1.  **Normalization**: Relative URLs are converted to absolute URLs using the current page's URL as a base.
2.  **Validation**: The absolute URL is checked against the base page's domain.
3.  **Discarding**: If the `netloc` does not match exactly, the link is discarded and never added to the crawl queue.

### 3. Crawler-Level Enforcement
The `SmolCrawler` class maintains the "seed domain" context throughout the crawl. When discovering new links, it compares them against the original `base_url` provided at the start of the crawl. This ensures that even if a page contains "domain-relative" links that might technically resolve to a different subdomain, they are still filtered out.

## Key Behavior Characteristics

| Feature | Behavior |
| :--- | :--- |
| **External Links** | Ignored |
| **Subdomains** | Ignored (e.g., `blog.example.com` is considered off-domain if starting at `example.com`) |
| **Port Numbers** | Must match (e.g., `example.com:8080` vs `example.com`) |
| **Redirects** | Followed, but subsequent link extraction from redirected pages is still constrained to the original domain |

## Rationale
This strategy prevents "crawl frontier explosion" where a small crawl could accidentally expand to the entire internet. It ensures that the resulting dataset is focused and relevant to the specific target site.
