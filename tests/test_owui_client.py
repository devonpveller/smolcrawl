"""Tests for the OWUI Knowledge Client (mocked HTTP)."""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from smolcrawl.owui_client import OwuiConfig, OwuiKnowledgeClient, SyncResult
from smolcrawl.db import Page


@pytest.fixture
def config():
    return OwuiConfig(
        base_url="http://localhost:3000",
        api_key="test-key-123",
        knowledge_base_name="Test KB",
        upload_concurrency=1,
        retry_attempts=1,
        retry_backoff_base=0.0,
        processing_timeout=5,
    )


@pytest.fixture
def client(config):
    c = OwuiKnowledgeClient(config)
    yield c
    c.close()


@pytest.fixture
def sample_pages():
    return [
        Page(url="https://example.com/a", title="Page A", content="# Hello\n\nWorld.", raw_html="<h1>Hello</h1>"),
        Page(url="https://example.com/b", title="Page B", content="# Bye\n\nLater.", raw_html="<h1>Bye</h1>"),
    ]


# --- content_hash ---

def test_content_hash_deterministic():
    h1 = OwuiKnowledgeClient._content_hash("hello")
    h2 = OwuiKnowledgeClient._content_hash("hello")
    assert h1 == h2


def test_content_hash_differs():
    h1 = OwuiKnowledgeClient._content_hash("hello")
    h2 = OwuiKnowledgeClient._content_hash("world")
    assert h1 != h2


# --- url_to_filename ---

def test_url_to_filename_basic():
    name = OwuiKnowledgeClient._url_to_filename("https://example.com/docs/intro")
    assert name.endswith(".md")
    assert "docs_intro" in name


def test_url_to_filename_root():
    name = OwuiKnowledgeClient._url_to_filename("https://example.com/")
    assert name == "index.md"


# --- manifest ---

def test_manifest_save_and_load(client, tmp_path):
    """Test manifest round-trip."""
    with patch.object(client, '_get_manifest_dir', return_value=str(tmp_path)):
        manifest = {
            "knowledge_base_id": "kb-123",
            "knowledge_base_name": "Test",
            "last_sync": "2026-01-01T00:00:00Z",
            "files": {
                "https://example.com/a": {
                    "content_hash": "abc123",
                    "owui_file_id": "file-1",
                    "last_updated": "2026-01-01T00:00:00Z",
                }
            },
        }
        client._save_manifest("Test", manifest)
        loaded = client._load_manifest("Test")
        assert loaded["knowledge_base_id"] == "kb-123"
        assert "https://example.com/a" in loaded["files"]


def test_manifest_missing_returns_empty(client, tmp_path):
    with patch.object(client, '_get_manifest_dir', return_value=str(tmp_path)):
        loaded = client._load_manifest("nonexistent")
        assert loaded == {"files": {}}


# --- find_knowledge_base ---

def test_find_kb_found(client):
    mock_kbs = [
        {"id": "kb-1", "name": "Other KB"},
        {"id": "kb-2", "name": "Test KB"},
    ]
    with patch.object(client, '_request_with_retry', return_value=mock_kbs):
        result = client.find_knowledge_base("Test KB")
        assert result["id"] == "kb-2"


def test_find_kb_not_found(client):
    with patch.object(client, '_request_with_retry', return_value=[]):
        result = client.find_knowledge_base("Missing")
        assert result is None


# --- create_knowledge_base ---

def test_create_kb(client):
    mock_resp = {"id": "kb-new", "name": "New KB"}
    with patch.object(client, '_request_with_retry', return_value=mock_resp):
        result = client.create_knowledge_base("New KB", "desc")
        assert result["id"] == "kb-new"


def test_create_kb_failure(client):
    with patch.object(client, '_request_with_retry', return_value=None):
        with pytest.raises(RuntimeError, match="Failed to create"):
            client.create_knowledge_base("Fail KB")


# --- get_or_create_knowledge_base ---

def test_get_or_create_existing(client):
    with patch.object(client, 'find_knowledge_base', return_value={"id": "kb-exist"}):
        kb_id = client.get_or_create_knowledge_base("Existing")
        assert kb_id == "kb-exist"


def test_get_or_create_new(client):
    with patch.object(client, 'find_knowledge_base', return_value=None):
        with patch.object(client, 'create_knowledge_base', return_value={"id": "kb-new"}):
            kb_id = client.get_or_create_knowledge_base("New")
            assert kb_id == "kb-new"


# --- upload_file ---

def test_upload_file(client):
    with patch.object(client, '_request_with_retry', return_value={"id": "file-abc"}):
        file_id = client.upload_file("test.md", b"# Hello")
        assert file_id == "file-abc"


def test_upload_file_failure(client):
    with patch.object(client, '_request_with_retry', return_value=None):
        with pytest.raises(RuntimeError, match="Failed to upload"):
            client.upload_file("test.md", b"content")


# --- wait_for_processing ---

def test_wait_for_processing_completed(client):
    resp = {"id": "file-1", "meta": {"status": "completed"}}
    with patch.object(client, '_request_with_retry', return_value=resp):
        result = client.wait_for_processing("file-1")
        assert result["id"] == "file-1"


def test_wait_for_processing_failed(client):
    resp = {"id": "file-1", "meta": {"status": "failed", "error": "bad file"}}
    with patch.object(client, '_request_with_retry', return_value=resp):
        with pytest.raises(RuntimeError, match="bad file"):
            client.wait_for_processing("file-1")


# --- sync_pages ---

def test_sync_pages_basic(client, sample_pages, tmp_path):
    """Test that sync uploads pages and creates a manifest."""
    with patch.object(client, 'get_or_create_knowledge_base', return_value="kb-test"):
        with patch.object(client, '_get_manifest_dir', return_value=str(tmp_path)):
            with patch.object(client, 'upload_file', return_value="file-1"):
                with patch.object(client, 'wait_for_processing', return_value={"id": "file-1"}):
                    with patch.object(client, 'add_file_to_knowledge_base', return_value={}):
                        result = client.sync_pages(sample_pages, "Test KB")

    assert result.knowledge_base_id == "kb-test"
    assert result.uploaded == 2
    assert result.skipped == 0
    assert result.failed == 0


def test_sync_pages_incremental_skip(client, sample_pages, tmp_path):
    """Test that unchanged pages are skipped on re-sync."""
    # Pre-populate manifest with matching hashes
    manifest_files = {}
    for page in sample_pages:
        content_hash = OwuiKnowledgeClient._content_hash(page.content)
        manifest_files[page.url] = {
            "content_hash": content_hash,
            "owui_file_id": f"existing-{page.url}",
            "last_updated": "2026-01-01T00:00:00Z",
        }
    manifest = {
        "knowledge_base_id": "kb-test",
        "knowledge_base_name": "Test KB",
        "last_sync": "2026-01-01T00:00:00Z",
        "files": manifest_files,
    }

    with patch.object(client, 'get_or_create_knowledge_base', return_value="kb-test"):
        with patch.object(client, '_get_manifest_dir', return_value=str(tmp_path)):
            # Save the manifest first
            client._save_manifest("Test KB", manifest)
            result = client.sync_pages(sample_pages, "Test KB")

    assert result.uploaded == 0
    assert result.skipped == 2


def test_sync_pages_with_progress(client, sample_pages, tmp_path):
    """Test that progress callback is called."""
    progress_calls = []

    def on_progress(current, total, filename):
        progress_calls.append((current, total, filename))

    with patch.object(client, 'get_or_create_knowledge_base', return_value="kb-test"):
        with patch.object(client, '_get_manifest_dir', return_value=str(tmp_path)):
            with patch.object(client, 'upload_file', return_value="file-1"):
                with patch.object(client, 'wait_for_processing', return_value={"id": "file-1"}):
                    with patch.object(client, 'add_file_to_knowledge_base', return_value={}):
                        client.sync_pages(sample_pages, "Test KB", on_progress=on_progress)

    assert len(progress_calls) == 2


# --- test_connection ---

def test_connection_success(client):
    with patch.object(client, '_request_with_retry', return_value=[]):
        assert client.test_connection() is True


def test_connection_failure(client):
    with patch.object(client, '_request_with_retry', return_value=None):
        assert client.test_connection() is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
