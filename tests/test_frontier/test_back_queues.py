import pytest
import asyncio
import time
from smolcrawl.frontier.models import URLEntry
from smolcrawl.frontier.back_queues import BackQueueManager

@pytest.mark.asyncio
async def test_back_queue_politeness():
    """Per-host delays are respected."""
    bq = BackQueueManager(default_delay=0.5)
    
    bq.add(URLEntry(priority=0, url="http://a.com/1", host="a.com"))
    bq.add(URLEntry(priority=0, url="http://a.com/2", host="a.com"))
    
    start = time.time()
    await bq.get()  # Immediate first request
    
    # Second request should be delayed
    await bq.get()
    elapsed = time.time() - start
    
    # Allow some tolerance for system scheduler
    assert 0.45 < elapsed < 0.65  # ~0.5 second delay

@pytest.mark.asyncio
async def test_back_queue_multi_host_scheduling():
    """Multiple hosts are interleaved based on readiness."""
    bq = BackQueueManager(default_delay=0.2)
    
    # Add to host A
    bq.add(URLEntry(priority=0, url="http://a.com/1", host="a.com")) # Ready @ T
    bq.add(URLEntry(priority=0, url="http://a.com/2", host="a.com")) # Ready @ T+0.2
    
    # Add to host B
    bq.add(URLEntry(priority=0, url="http://b.com/1", host="b.com")) # Ready @ T
    
    # Should get A1, B1 (both ready), then A2 (delayed)
    # The order of A1, B1 is heap tie-breaking, effectively random or insertion order
    
    r1 = await bq.get()
    r2 = await bq.get()
    r3 = await bq.get()
    
    hosts = {r1.host, r2.host}
    assert "a.com" in hosts
    assert "b.com" in hosts
    
    assert r3.host == "a.com"

@pytest.mark.asyncio
async def test_back_queue_custom_delays():
    """Custom host delays are respected."""
    bq = BackQueueManager(default_delay=0.1, host_delays={"slow.com": 0.5})
    
    bq.add(URLEntry(priority=0, url="http://slow.com/1", host="slow.com"))
    bq.add(URLEntry(priority=0, url="http://slow.com/2", host="slow.com"))
    
    start = time.time()
    await bq.get()
    await bq.get()
    elapsed = time.time() - start
    
    assert elapsed >= 0.5

@pytest.mark.asyncio
async def test_back_queue_empty():
    bq = BackQueueManager()
    assert await bq.get() is None
    assert bq.is_empty()
