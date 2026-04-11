FROM ghcr.io/open-webui/pipelines:main

# Install Node.js for readabilipy
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Install SmolCrawl
RUN pip install --no-cache-dir smolcrawl

# Copy the pipeline definition
COPY smolcrawl_pipeline.py /app/pipelines/

EXPOSE 9099
