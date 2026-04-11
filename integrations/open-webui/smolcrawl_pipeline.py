"""
title: SmolCrawl Knowledge Builder
author: smolcrawl
date: 2026-04-10
version: 1.0
license: MIT
description: Crawl a website, augment markdown for RAG, and upload to an OWUI knowledge collection. Streams progress in chat.
requirements: smolcrawl, httpx, markdownify, readabilipy, beautifulsoup4, lxml
"""

import queue
import re
import threading
from typing import Generator, Iterator, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel


class Pipeline:
    """OWUI Pipeline that crawls a website and uploads to a knowledge base."""

    class Valves(BaseModel):
        """User-configurable settings shown in OWUI admin panel."""
        owui_base_url: str = "http://localhost:3000"
        owui_api_key: str = ""
        knowledge_base_name: str = ""
        server_intensity: float = 0.3
        max_pages: int = 200
        upload_concurrency: int = 3
        augment_for_rag: bool = True

    def __init__(self):
        self.name = "SmolCrawl Knowledge Builder"
        self.valves = self.Valves()

    async def on_startup(self):
        """Verify smolcrawl is importable."""
        try:
            import smolcrawl  # noqa: F401
        except ImportError:
            print("[SmolCrawl Pipeline] WARNING: smolcrawl package not found. "
                  "Install with: pip install smolcrawl")

    async def on_shutdown(self):
        pass

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, Generator[str, None, None], Iterator[str]]:
        """Process a user message containing a URL to crawl.

        Streams progress as markdown-formatted status updates.
        """
        url = self._extract_url(user_message)
        if not url:
            return ("Please provide a URL to crawl.\n\n"
                    "Example: `crawl https://docs.example.com`")

        return self._run_pipeline(url)

    def _run_pipeline(self, url: str) -> Generator[str, None, None]:
        """Execute the full crawl → augment → upload pipeline with streaming."""
        from smolcrawl.crawl import crawl_target_sync
        from smolcrawl.augment import augment_pages
        from smolcrawl.owui_client import OwuiConfig, OwuiKnowledgeClient

        domain = urlparse(url).netloc
        kb_name = self.valves.knowledge_base_name or f"SmolCrawl - {domain}"

        yield f"## SmolCrawl Pipeline\n\n"
        yield f"**Target:** {url}\n"
        yield f"**Knowledge Base:** {kb_name}\n"
        yield f"**Max Pages:** {self.valves.max_pages}\n\n"

        # Phase 1: Crawl
        yield f"### Phase 1: Crawling\n\n"
        try:
            intensity = self.valves.server_intensity
            max_concurrent = max(1, int(1 + (intensity * 11)))
            delay = (1.0 - intensity) * 2.0
            pages = crawl_target_sync(
                url,
                max_pages=self.valves.max_pages,
                max_concurrent=max_concurrent,
                delay=delay,
            )
            yield f"Crawled **{len(pages)}** pages.\n\n"
        except Exception as e:
            yield f"**Error during crawl:** {e}\n"
            return

        if not pages:
            yield "No pages found. Check the URL and try again.\n"
            return

        # Phase 2: Augment
        if self.valves.augment_for_rag:
            yield f"### Phase 2: Augmenting for RAG\n\n"
            try:
                pages = augment_pages(pages)
                yield f"Augmented **{len(pages)}** pages with metadata.\n\n"
            except Exception as e:
                yield f"**Warning:** Augmentation failed ({e}), uploading raw content.\n\n"

        # Phase 3: Upload
        yield f"### Phase 3: Uploading to Knowledge Base\n\n"
        config = OwuiConfig(
            base_url=self.valves.owui_base_url,
            api_key=self.valves.owui_api_key,
            knowledge_base_name=kb_name,
            upload_concurrency=self.valves.upload_concurrency,
        )

        progress_queue: queue.Queue = queue.Queue()
        result_holder: list = []
        error_holder: list = []

        def upload_worker():
            try:
                with OwuiKnowledgeClient(config) as client:
                    result = client.sync_pages(
                        pages, kb_name,
                        on_progress=lambda cur, tot, name:
                            progress_queue.put((cur, tot, name)),
                    )
                    result_holder.append(result)
            except Exception as e:
                error_holder.append(str(e))
            finally:
                progress_queue.put(None)  # sentinel

        thread = threading.Thread(target=upload_worker, daemon=True)
        thread.start()

        while True:
            item = progress_queue.get()
            if item is None:
                break
            cur, tot, name = item
            yield f"Uploading: {cur}/{tot} — {name}\n"

        thread.join(timeout=30)

        if error_holder:
            yield f"\n**Upload error:** {error_holder[0]}\n"
            return

        # Summary
        if result_holder:
            result = result_holder[0]
            yield f"\n### Complete!\n\n"
            yield f"| Metric | Value |\n|--------|-------|\n"
            yield f"| Pages crawled | {len(pages)} |\n"
            yield f"| Files uploaded | {result.uploaded} |\n"
            yield f"| Files skipped (unchanged) | {result.skipped} |\n"
            yield f"| Failures | {result.failed} |\n"
            yield f"| Knowledge Base | {kb_name} |\n"
        else:
            yield "\n**Upload completed** (no result details available).\n"

    @staticmethod
    def _extract_url(message: str) -> Optional[str]:
        """Extract the first URL from a user message."""
        # Try to find an explicit URL
        url_pattern = re.compile(
            r'https?://[^\s<>\'")\]]+',
            re.IGNORECASE,
        )
        match = url_pattern.search(message)
        if match:
            return match.group(0).rstrip('.,;:!?')
        return None
