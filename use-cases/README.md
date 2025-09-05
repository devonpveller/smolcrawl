# Use Cases

This directory contains organized use case implementations for specific document processing scenarios. Each use case is self-contained with its own documentation and configuration.

## Available Use Cases

### 📘 [Blueprint API Processing](./blueprint-api/)
**Purpose**: Process Unreal Engine 5.4 Blueprint API documentation from local HTML files

**Key Features**:
- Local HTTP server for serving UE5.4 documentation
- Automated URL discovery from Blueprint API structure
- Windows-compatible batch processing scripts
- Real-time progress monitoring
- Categorized output (Classes, Components, Other)

**Main Files**: `blueprint_api_assistant.py`, `process_blueprint_api.py`, `discover_blueprint_urls_win.py`

### 🔧 [Document Processing](./document-processing/)
**Purpose**: General-purpose document processing, HTML to Markdown conversion, and web crawling

**Key Features**:
- Universal document processor with multiple modes
- Multi-threaded processing with configurable workers
- Intelligent content extraction using readability algorithms
- Batch processing and progress monitoring
- Cross-platform compatibility with Windows fixes

**Main Files**: `doc_processor.py`, `batch_processor.py`, `complete_extractor.py`

### 🎮 [Unreal Documentation](./unreal-docs/)
**Purpose**: Specialized processing for Unreal Engine documentation

**Key Features**:
- Document merging for fragmented Unreal docs
- JSON and YAML configuration support
- Unreal-specific document structure handling
- Integration with Blueprint API processing

**Main Files**: `merge_unreal_docs.py`, `config_unreal.json`, `config_unreal.yaml`

## Quick Start Guide

1. **Choose your use case** based on your documentation processing needs
2. **Navigate to the use case directory**: `cd use-cases/[use-case-name]/`
3. **Read the specific README**: Each use case has detailed documentation
4. **Configure**: Set up configuration files as needed
5. **Execute**: Run the main processing scripts

## Use Case Selection Guide

| Need | Recommended Use Case |
|------|---------------------|
| Process UE5.4 Blueprint API docs | [blueprint-api](./blueprint-api/) |
| General web documentation extraction | [document-processing](./document-processing/) |
| Merge Unreal Engine documentation | [unreal-docs](./unreal-docs/) |
| Convert HTML to Markdown | [document-processing](./document-processing/) |
| Large-scale documentation processing | [document-processing](./document-processing/) |

## Configuration

Each use case includes:
- **README.md**: Detailed usage instructions
- **Configuration files**: JSON/YAML configs for processing parameters
- **Example scripts**: Sample implementations and batch files
- **Utility scripts**: Supporting tools and helpers

## Integration

Use cases can work together:
- **Blueprint API** + **Document Processing**: Extract and further process Blueprint docs
- **Unreal Docs** + **Document Processing**: Comprehensive Unreal documentation workflows
- **Cross-use case**: Share configurations and output between different use cases

## Support

For use case-specific questions:
1. Check the individual use case README files
2. Review configuration examples in each directory
3. Run test scripts to validate functionality
4. Check the main project documentation in `/docs/`
