# Unreal Engine Documentation Processing

This directory contains tools specifically for processing Unreal Engine documentation.

## Files

### Document Merging
- `merge_unreal_docs.py` - Merges multiple Unreal documentation files into unified documents

### Configuration
- `config_unreal.json` - JSON configuration for Unreal documentation processing
- `config_unreal.yaml` - YAML configuration for Unreal documentation processing

## Purpose

This use case focuses on:
- Merging fragmented Unreal Engine documentation
- Creating comprehensive documentation sets
- Processing Unreal-specific document structures
- Maintaining proper documentation hierarchy

## Usage

1. Configure processing parameters in `config_unreal.json` or `config_unreal.yaml`
2. Run `merge_unreal_docs.py` to process and merge documentation
3. Output will be generated according to configuration settings

## Related

This use case works in conjunction with:
- Blueprint API processing (../blueprint-api/)
- General document processing tools (../document-processing/)
