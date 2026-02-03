# Bing Grounding MCP Server - Docker Image
# 
# Build: docker build -t bing-mcp-server .
# Run: docker run -p 8000:8000 --env-file .env bing-mcp-server

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (override at runtime)
ENV PROJECT_ENDPOINT=""
ENV BING_CONNECTION_NAME=""
ENV MODEL_DEPLOYMENT_NAME="gpt-4o"
ENV PORT=8000

# Expose port for HTTP transport
EXPOSE 8000

# Run the MCP server
CMD ["python", "mcp_server.py"]
