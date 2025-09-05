from typing import List, Optional
from loguru import logger
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
import readabilipy.simple_json
import markdownify
import os
import platform

from crawlee.http_clients import HttpResponse

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
        from urllib.parse import urlparse

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


def extract_from_response(url: str, response: HttpResponse) -> Page | None:
    try:
        raw_bytes = response.read()
        raw_html = raw_bytes.decode("utf-8")
        if "<title>" in raw_html:
            title = raw_html.split("<title>")[1].split("</title>")[0]
        else:
            title = ""
        content = extract_content_from_html(raw_html)
        return Page(url=url, title=title, content=content, raw_html=raw_html)
    except Exception as e:
        logger.error(f"Error extracting from response: {e}")
        return None


async def crawl_target(target_url: str) -> List[Page]:
    logger.info(f"Starting crawl of {target_url}")
    # BeautifulSoupCrawler crawls the web using HTTP requests
    # and parses HTML using the BeautifulSoup library.
    crawler = BeautifulSoupCrawler()
    cache = get_cache("crawl")

    pages = cache.get(target_url)
    if pages:
        return [Page(**page) for page in pages]

    pages: List[Page] = []

    # Define a request handler to process each crawled page
    # and attach it to the crawler using a decorator.
    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        page = extract_from_response(context.request.url, context.http_response)
        if page:
            pages.append(page)
        # Extract links from the current page and add them to the crawling queue.
        await context.enqueue_links()

    # Add first URL to the queue and start the crawl.
    await crawler.run([target_url])

    pages_as_dicts = [page.model_dump() for page in pages]
    logger.success(f"Crawled {len(pages)} pages from {target_url}")
    cache.set(target_url, pages_as_dicts, expire=72.0 * 3600)
    return pages
