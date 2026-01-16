import pytest
from smolcrawl.frontier.models import URLEntry
from smolcrawl.frontier.front_queues import FrontQueueManager

def test_front_queue_priority_ordering():
    """URLs are distributed by depth to correct priority queues."""
    fq = FrontQueueManager(num_queues=4)
    
    fq.add(URLEntry(priority=0, url="http://a.com", depth=0))  # Priority 0
    fq.add(URLEntry(priority=0, url="http://b.com", depth=3))  # Priority 1
    fq.add(URLEntry(priority=0, url="http://c.com", depth=6))  # Priority 3 (max)
    
    assert len(fq.queues[0]) == 1  # depth 0 -> priority 0
    assert len(fq.queues[1]) == 1  # depth 3 -> priority 1
    assert len(fq.queues[3]) == 1  # depth 6 -> priority 3
    assert fq.total_urls == 3

def test_front_queue_weighted_selection():
    """Higher priority queues should be selected more often (probabilistic)."""
    fq = FrontQueueManager(num_queues=2, priority_weights=[0.9, 0.1])
    
    # Add many items to both queues
    for i in range(100):
        fq.add(URLEntry(priority=0, url=f"http://high.com/{i}", depth=0)) # Priority 0
        fq.add(URLEntry(priority=0, url=f"http://low.com/{i}", depth=4))  # Priority 1
        
    high_priority_count = 0
    for _ in range(100):
        entry = fq.get()
        if entry.depth == 0:
            high_priority_count += 1
            
    # Should get significantly more high priority items
    assert high_priority_count > 70

def test_front_queue_empty():
    fq = FrontQueueManager()
    assert fq.get() is None
    assert fq.is_empty()

def test_front_queue_depth_mapping():
    fq = FrontQueueManager(num_queues=3)
    # 0 // 2 = 0 -> 0
    # 1 // 2 = 0 -> 0
    # 2 // 2 = 1 -> 1
    # 3 // 2 = 1 -> 1
    # 4 // 2 = 2 -> 2
    # 5 // 2 = 2 -> 2
    # 6 // 2 = 3 -> 2 (capped at num_queues - 1)
    
    assert fq._depth_to_priority(0) == 0
    assert fq._depth_to_priority(1) == 0
    assert fq._depth_to_priority(2) == 1
    assert fq._depth_to_priority(3) == 1
    assert fq._depth_to_priority(4) == 2
    assert fq._depth_to_priority(6) == 2
