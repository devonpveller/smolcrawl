FROM ghcr.io/open-webui/pipelines:main

# Install Node.js for readabilipy content extraction
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Install SmolCrawl from local source (PyPI version is stale and pulls crawlee)
COPY pyproject.toml README.md /tmp/smolcrawl/
COPY src /tmp/smolcrawl/src
RUN pip install --no-cache-dir /tmp/smolcrawl && rm -rf /tmp/smolcrawl

# Copy the pipeline definition
COPY integrations/open-webui/smolcrawl_pipeline.py /app/pipelines/

EXPOSE 9099
