"""
SmolCrawl - Lightweight Web Crawler
===================================
Async web crawler using httpx + BeautifulSoup for recursive crawling.
No heavy dependencies - replaces crawlee for simpler, more compatible crawling.
"""

from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
import asyncio
import time

from loguru import logger
from bs4 import BeautifulSoup
import httpx
import readabilipy.simple_json
import markdownify
import os
import platform

from .utils import get_cache
from .db import Page


# Apply Windows fix for readabilipy if needed
if platform.system() == 'Windows':
    import subprocess
    import readabilipy.utils
    import readabilipy.simple_json

    def _patched_have_npm():
        """Patched version of have_npm that works on Windows"""
        try:
            cp = subprocess.run(
                ["npm", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                shell=True  # This is the key fix for Windows
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
        return cp.returncode == 0

    def _patched_run_npm_install():
        """Patched version of run_npm_install that works on Windows"""
        import readabilipy.simple_json
        
        # Get the javascript directory path
        jsdir = os.path.join(os.path.dirname(readabilipy.simple_json.__file__), 'javascript')
        
        try:
            subprocess.run(
                ["npm", "install"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                shell=True,  # This is the key fix for Windows
                cwd=jsdir  # Run in the javascript directory where package.json is
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _patched_have_node():
        """Check that we can run node and have a new enough version (Windows-compatible)"""
        try:
            cp = subprocess.run(
                ['node', '-v'], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=False,
                shell=True  # This is the key fix for Windows
            )
        except FileNotFoundError:
            return False
        if not cp.returncode == 0:
            return False
        major = int(cp.stdout.split(b'.')[0].lstrip(b'v'))
        if major < 10:
            return False
        # check that this package has a node_modules dir in the javascript
        # directory, if it doesn't, it wasn't installed with Node support
        jsdir = os.path.join(os.path.dirname(readabilipy.simple_json.__file__), 'javascript')
        node_modules = os.path.join(jsdir, 'node_modules')
        if not os.path.exists(node_modules):
            # Try installing node dependencies.
            readabilipy.simple_json.run_npm_install()
        return os.path.exists(node_modules)

    # Apply the monkey patches
    readabilipy.utils.have_npm = _patched_have_npm
    readabilipy.utils.run_npm_install = _patched_run_npm_install
    readabilipy.simple_json.have_node = _patched_have_node
    readabilipy.simple_json.run_npm_install = _patched_run_npm_install
    
    logger.debug("Applied Windows fix for readabilipy Node.js detection")


def replace_domain(url: str, domain_override: Optional[str]) -> str:
    if domain_override:
        parsed_url = urlparse(url)
        new_netloc = urlparse(domain_override).netloc

        # Reconstruct the URL with the new netloc
        new_url = parsed_url._replace(netloc=new_netloc).geturl()
        return new_url
    return url


def extract_content_from_html(html: str) -> str:
    """Extract and convert HTML content to Markdown format.

    Args:
        html: Raw HTML content to process

    Returns:
        Simplified markdown version of the content
    """
    ret = readabilipy.simple_json.simple_json_from_html_string(
        html, use_readability=True
    )
    if not ret["content"]:
        return "<error>Page failed to be simplified from HTML</error>"
    content = markdownify.markdownify(
        ret["content"],
        heading_style=markdownify.ATX,
    )
    return content


def extract_from_html(url: str, raw_html: str) -> Page | None:
    """Extract a Page object from raw HTML content.
    
    Args:
        url: The URL the HTML was fetched from
        raw_html: The raw HTML content
        
    Returns:
        Page object or None if extraction failed
    """
    try:
        if "<title>" in raw_html:
            title = raw_html.split("<title>")[1].split("</title>")[0]
        else:
            title = ""
        content = extract_content_from_html(raw_html)
        return Page(url=url, title=title, content=content, raw_html=raw_html)
    except Exception as e:
        logger.error(f"Error extracting from HTML: {e}")
        return None


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if URL belongs to the same domain as the base URL."""
    try:
        url_parsed = urlparse(url)
        base_parsed = urlparse(base_url)
        return url_parsed.netloc == base_parsed.netloc
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and trailing slashes."""
    parsed = urlparse(url)
    # Remove fragment, normalize path
    normalized = parsed._replace(fragment='')
    result = normalized.geturl().rstrip('/')
    return result


def extract_links(html: str, base_url: str) -> Set[str]:
    """Extract all valid links from HTML content.
    
    Args:
        html: Raw HTML content
        base_url: Base URL for resolving relative links
        
    Returns:
        Set of normalized absolute URLs from the same domain
    """
    links = set()
    try:
        soup = BeautifulSoup(html, 'lxml')
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            
            # Skip empty, javascript, mailto, tel links
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
                
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            
            # Only include same-domain URLs
            if is_same_domain(absolute_url, base_url):
                # Normalize and add
                normalized = normalize_url(absolute_url)
                if normalized:
                    links.add(normalized)
    except Exception as e:
        logger.warning(f"Error extracting links from {base_url}: {e}")
    
    return links


class SmolCrawler:
    """Lightweight async web crawler using httpx + BeautifulSoup.
    
    Features:
        - Async HTTP requests with connection pooling
        - Automatic link discovery and queueing
        - Rate limiting and retry logic
        - Same-domain URL filtering
        - Disk caching of results
        
    Example:
        >>> crawler = SmolCrawler(max_pages=100, delay=0.1)
        >>> pages = await crawler.crawl("https://docs.example.com")
    """
    
    def __init__(
        self,
        max_pages: int = 500,
        max_concurrent: int = 10,
        delay: float = 0.1,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "SmolCrawl/1.0 (https://github.com/bllchmbrs/smolcrawl)",
    ):
        """Initialize the crawler.
        
        Args:
            max_pages: Maximum number of pages to crawl
            max_concurrent: Maximum concurrent HTTP requests
            delay: Delay between requests (seconds) for rate limiting
            timeout: HTTP request timeout (seconds)
            max_retries: Maximum retries for failed requests
            user_agent: User-Agent header for requests
        """
        self.max_pages = max_pages
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        
        # State
        self.visited: Set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pages: List[Page] = []
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self.last_request_time: float = 0
        
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        if self.delay > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)
        self.last_request_time = time.time()
    
    async def _fetch_url(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Fetch a URL with retries and error handling.
        
        Args:
            client: httpx async client
            url: URL to fetch
            
        Returns:
            HTML content or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit()
                response = await client.get(url, follow_redirects=True)
                
                # Check for HTML content
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type.lower():
                    logger.debug(f"Skipping non-HTML: {url} ({content_type})")
                    return None
                    
                response.raise_for_status()
                return response.text
                
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {url}")
                return None  # Don't retry HTTP errors
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e} (attempt {attempt + 1}/{self.max_retries})")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
                
        return None
    
    async def _process_url(self, client: httpx.AsyncClient, url: str, base_url: str):
        """Process a single URL: fetch, extract content, discover links.
        
        Args:
            client: httpx async client
            url: URL to process
            base_url: Original base URL for same-domain checking
        """
        async with self.semaphore:
            html = await self._fetch_url(client, url)
            if not html:
                return
                
            # Extract page content
            page = extract_from_html(url, html)
            if page:
                self.pages.append(page)
                logger.debug(f"Extracted: {page.title[:50]}... ({url})")
            
            # Discover and queue new links
            links = extract_links(html, url)
            for link in links:
                if link not in self.visited and len(self.visited) < self.max_pages:
                    self.visited.add(link)
                    await self.queue.put(link)
    
    async def crawl(self, start_url: str) -> List[Page]:
        """Crawl a website starting from the given URL.
        
        Args:
            start_url: Starting URL for the crawl
            
        Returns:
            List of extracted Page objects
        """
        logger.info(f"Starting crawl of {start_url} (max {self.max_pages} pages)")
        start_time = time.time()
        
        # Normalize start URL
        start_url = normalize_url(start_url)
        self.visited.add(start_url)
        await self.queue.put(start_url)
        
        # Configure HTTP client
        headers = {"User-Agent": self.user_agent}
        limits = httpx.Limits(max_connections=self.max_concurrent * 2)
        
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout,
            limits=limits,
            http2=True,
        ) as client:
            
            while not self.queue.empty() and len(self.pages) < self.max_pages:
                # Process URLs in batches
                batch_size = min(self.max_concurrent, self.queue.qsize())
                tasks = []
                
                for _ in range(batch_size):
                    if self.queue.empty():
                        break
                    url = await self.queue.get()
                    tasks.append(self._process_url(client, url, start_url))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                # Progress update
                if len(self.pages) % 10 == 0 and self.pages:
                    elapsed = time.time() - start_time
                    rate = len(self.pages) / elapsed if elapsed > 0 else 0
                    logger.info(f"Progress: {len(self.pages)} pages ({rate:.1f} pages/sec)")
        
        elapsed = time.time() - start_time
        logger.success(f"Crawled {len(self.pages)} pages from {start_url} in {elapsed:.1f}s")
        return self.pages


async def crawl_target(
    target_url: str,
    max_pages: int = 500,
    max_concurrent: int = 10,
    delay: float = 0.1,
    use_cache: bool = True,
) -> List[Page]:
    """Crawl a target URL and return extracted pages.
    
    This is the main entry point for crawling. It uses disk caching
    to avoid re-crawling the same URL within 72 hours.
    
    Args:
        target_url: The URL to start crawling from
        max_pages: Maximum number of pages to crawl
        max_concurrent: Maximum concurrent HTTP requests
        delay: Delay between requests (seconds)
        use_cache: Whether to use disk cache for results
        
    Returns:
        List of Page objects with extracted content
        
    Example:
        >>> import asyncio
        >>> pages = asyncio.run(crawl_target("https://docs.example.com"))
        >>> print(f"Crawled {len(pages)} pages")
    """
    logger.info(f"Starting crawl of {target_url}")
    cache = get_cache("crawl")

    # Check cache first
    if use_cache:
        cached_pages = cache.get(target_url)
        if cached_pages:
            logger.info(f"Using cached results for {target_url} ({len(cached_pages)} pages)")
            return [Page(**page) for page in cached_pages]

    # Run the crawler
    crawler = SmolCrawler(
        max_pages=max_pages,
        max_concurrent=max_concurrent,
        delay=delay,
    )
    pages = await crawler.crawl(target_url)

    # Cache results
    if use_cache and pages:
        pages_as_dicts = [page.model_dump() for page in pages]
        logger.debug(f"Caching {len(pages)} pages for {target_url}")
        cache.set(target_url, pages_as_dicts, expire=72.0 * 3600)
    
    return pages


# Convenience function for sync usage
def crawl_target_sync(
    target_url: str,
    max_pages: int = 500,
    max_concurrent: int = 10,
    delay: float = 0.1,
    use_cache: bool = True,
) -> List[Page]:
    """Synchronous wrapper for crawl_target.
    
    Use this when you need to crawl from synchronous code.
    
    Args:
        target_url: The URL to start crawling from
        max_pages: Maximum number of pages to crawl
        max_concurrent: Maximum concurrent HTTP requests
        delay: Delay between requests (seconds)
        use_cache: Whether to use disk cache for results
        
    Returns:
        List of Page objects with extracted content
    """
    return asyncio.run(crawl_target(
        target_url,
        max_pages=max_pages,
        max_concurrent=max_concurrent,
        delay=delay,
        use_cache=use_cache,
    ))
