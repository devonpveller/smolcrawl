"""
title: Deep Research
author: smolcrawl
date: 2026-04-12
version: 1.0
license: MIT
description: Iterative RAG research with LLM-guided domain discovery, web search exploration, and chain-of-thought synthesis. Provides research() for quick exploration and deep_research() for full knowledge building.
requirements: httpx, pydantic
"""

# Re-export the Tools class for Open WebUI function discovery.
# OWUI expects a `class Tools` with Valves at the module level.
from deep_research import Tools

__all__ = ["Tools"]
