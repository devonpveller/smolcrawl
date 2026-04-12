"""
Deep Research Function for Open WebUI.

Provides iterative RAG research with LLM-guided domain discovery,
web search exploration, and chain-of-thought synthesis.

Entry point: deep_research_function.py (parent directory) imports
the Tools class from this package.
"""

from .function import Tools

__all__ = ["Tools"]
