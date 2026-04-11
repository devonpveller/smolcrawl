"""Tests for the markdown RAG augmenter module."""

import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from smolcrawl.augment import (
    check_header_patterns,
    determine_header_level_by_context,
    convert_to_proper_header,
    guess_aliases_from_heading,
    build_metadata_block,
    augment_markdown,
    augment_pages,
)
from smolcrawl.db import Page


# --- check_header_patterns ---

def test_markdown_header():
    result = check_header_patterns('## My Section')
    assert result == ('markdown', 'My Section')


def test_bold_header():
    result = check_header_patterns('**Installation Guide**')
    assert result == ('bold', 'Installation Guide')


def test_colon_header():
    result = check_header_patterns('Meeting:')
    assert result == ('colon', 'Meeting')


def test_date_header():
    result = check_header_patterns('2025 07 15')
    assert result == ('date', '2025 07 15')


def test_numbered_header():
    result = check_header_patterns('1. John Smith')
    assert result == ('numbered', '1. John Smith')


def test_allcaps_header():
    result = check_header_patterns('CONFIGURATION SETTINGS')
    assert result == ('allcaps', 'CONFIGURATION SETTINGS')


def test_allcaps_stopword_ignored():
    """ALL CAPS stop words like NOTE should not be treated as headers."""
    result = check_header_patterns('NOTE')
    assert result is None


def test_empty_line():
    result = check_header_patterns('')
    assert result is None


def test_regular_text():
    result = check_header_patterns('This is a regular paragraph of text.')
    assert result is None


# --- determine_header_level_by_context ---

def test_bold_at_root_is_level_1():
    level = determine_header_level_by_context([], 'bold', 'Title')
    assert level == 1


def test_bold_nested_is_level_2():
    level = determine_header_level_by_context([(1, 'Top')], 'bold', 'Sub')
    assert level == 2


def test_date_is_level_1_or_2():
    level = determine_header_level_by_context([], 'date', '2025 07 15')
    assert level in (1, 2)


def test_numbered_at_root():
    level = determine_header_level_by_context([], 'numbered', '1. Item')
    assert level == 2


def test_colon_nested():
    level = determine_header_level_by_context([(1, 'A'), (2, 'B')], 'colon', 'Details')
    assert level == 3


# --- convert_to_proper_header ---

def test_convert_bold():
    result = convert_to_proper_header('Installation Guide', 1, 'bold')
    assert result == '# Installation Guide'


def test_convert_allcaps_titlecase():
    result = convert_to_proper_header('CONFIGURATION SETTINGS', 2, 'allcaps')
    assert result == '## Configuration Settings'


def test_convert_colon_removes_trailing_colon():
    result = convert_to_proper_header('Meeting:', 2, 'colon')
    assert result == '## Meeting'


# --- guess_aliases_from_heading ---

def test_aliases_basic():
    result = guess_aliases_from_heading('Installation Guide for Unreal Engine')
    assert 'Installation' in result
    assert 'Guide' in result
    assert 'Unreal' in result
    assert 'Engine' in result


def test_aliases_max_five():
    result = guess_aliases_from_heading('Alpha Beta Gamma Delta Epsilon Zeta Eta Theta')
    parts = [p.strip() for p in result.split(',')]
    assert len(parts) <= 5


def test_aliases_skips_short_words():
    result = guess_aliases_from_heading('A to Z Guide')
    assert 'to' not in result.lower().split(', ')


# --- build_metadata_block ---

def test_metadata_block_basic():
    block = build_metadata_block(
        doc_title='My Doc',
        source_url='https://example.com/page',
        breadcrumb=[(1, 'Top'), (2, 'Section')],
        aliases='Top, Section',
    )
    assert '[DocTitle: My Doc]' in block
    assert '[Path: https://example.com/page]' in block
    assert '[Section: Top > Section]' in block
    assert '[Aliases: Top, Section]' in block


def test_metadata_block_empty_aliases():
    block = build_metadata_block(
        doc_title='My Doc',
        source_url='https://example.com',
        breadcrumb=[],
        aliases='',
    )
    assert '[Aliases:' not in block


# --- augment_markdown ---

def test_augment_preserves_plain_text():
    md = 'Hello world\n\nThis is a paragraph.'
    result = augment_markdown(md)
    assert 'Hello world' in result
    assert 'This is a paragraph.' in result


def test_augment_injects_metadata_after_header():
    md = '# Welcome\n\nSome content here.'
    result = augment_markdown(md, source_url='https://example.com', doc_title='Test')
    assert '[DocTitle: Test]' in result
    assert '[Path: https://example.com]' in result
    assert '[Section: Welcome]' in result


def test_augment_converts_bold_to_header():
    md = '**Getting Started**\n\nFollow these steps.'
    result = augment_markdown(md, source_url='test.md', doc_title='Guide')
    assert '# Getting Started' in result
    assert '[DocTitle: Guide]' in result


def test_augment_tracks_breadcrumb():
    md = '# Top\n\nIntro.\n\n## Sub\n\nDetails.'
    result = augment_markdown(md, source_url='x.md', doc_title='Doc')
    assert '[Section: Top > Sub]' in result


def test_augment_auto_detects_title():
    md = '# Auto Title\n\nBody text.'
    result = augment_markdown(md)
    assert '[DocTitle: Auto Title]' in result


# --- augment_pages ---

def test_augment_pages_batch():
    pages = [
        Page(url='https://example.com/a', title='Page A', content='# Hello\n\nWorld.', raw_html='<h1>Hello</h1>'),
        Page(url='https://example.com/b', title='Page B', content='Some text only.', raw_html='<p>Some text</p>'),
    ]
    result = augment_pages(pages)
    assert len(result) == 2
    assert result[0].url == 'https://example.com/a'
    assert '[DocTitle: Page A]' in result[0].content
    # Page B has no headers, so content mostly passes through
    assert 'Some text only.' in result[1].content


def test_augment_pages_immutability():
    """Augmented pages should be new objects, not mutated originals."""
    original = Page(url='https://x.com', title='T', content='# H\n\nBody.', raw_html='')
    result = augment_pages([original])
    assert result[0] is not original
    assert '[DocTitle:' in result[0].content
    assert '[DocTitle:' not in original.content


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
