#!/bin/bash
# =============================================================================
# Bing Grounding MCP Server - Build and Run Script
# =============================================================================
# This script builds and runs the local MCP server Docker container.
# 
# Usage:
#   ./run-mcp-server.sh          # Build and run
#   ./run-mcp-server.sh --build  # Force rebuild
#   ./run-mcp-server.sh --stop   # Stop the container
#   ./run-mcp-server.sh --logs   # View container logs
#   ./run-mcp-server.sh --status # Check server status
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="bing-mcp-server-http"
CONTAINER_NAME="bing-mcp-server"
PORT=8000
ENV_FILE="$PROJECT_ROOT/.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Check if environment file exists
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_warning "Environment file not found at $ENV_FILE"
        log_info "Checking for .env.example..."
        
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            log_info "Copying .env.example to .env"
            cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
            log_warning "Please update $ENV_FILE with your actual values"
        else
            log_error "No .env or .env.example found. Please create $ENV_FILE"
            exit 1
        fi
    fi
}

# Build the Docker image
build_image() {
    log_info "Building Docker image: $IMAGE_NAME..."
    cd "$SCRIPT_DIR"
    docker build -f Dockerfile.http -t "$IMAGE_NAME" .
    log_success "Docker image built successfully"
}

# Stop and remove existing container
stop_container() {
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Stopping running container: $CONTAINER_NAME..."
        docker stop "$CONTAINER_NAME" > /dev/null
        log_success "Container stopped"
    fi
    
    if docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Removing container: $CONTAINER_NAME..."
        docker rm "$CONTAINER_NAME" > /dev/null
        log_success "Container removed"
    fi
}

# Run the container
run_container() {
    log_info "Starting container: $CONTAINER_NAME on port $PORT..."
    docker run -d \
        -p "$PORT:$PORT" \
        --env-file "$ENV_FILE" \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        "$IMAGE_NAME"
    
    log_success "Container started"
}

# Check health status
check_health() {
    log_info "Waiting for server to be ready..."
    
    for i in {1..10}; do
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health")
            log_success "Server is healthy!"
            echo -e "${GREEN}Health response: $HEALTH_RESPONSE${NC}"
            return 0
        fi
        sleep 1
    done
    
    log_error "Server health check failed after 10 seconds"
    log_info "Container logs:"
    docker logs "$CONTAINER_NAME" --tail 20
    return 1
}

# Show container logs
show_logs() {
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        docker logs "$CONTAINER_NAME" -f
    else
        log_error "Container $CONTAINER_NAME is not running"
        exit 1
    fi
}

# Show status
show_status() {
    echo ""
    echo "=== MCP Server Status ==="
    echo ""
    
    # Check if container exists and is running
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_success "Container is running"
        docker ps -f name="$CONTAINER_NAME" --format "table {{.ID}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        
        # Check health
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health")
            log_success "Health check passed: $HEALTH_RESPONSE"
        else
            log_warning "Health endpoint not responding"
        fi
    elif docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
        log_warning "Container exists but is stopped"
        log_info "Run './run-mcp-server.sh' to start it"
    else
        log_warning "Container does not exist"
        log_info "Run './run-mcp-server.sh' to build and start"
    fi
    
    echo ""
    echo "=== Configuration ==="
    echo "Image:     $IMAGE_NAME"
    echo "Container: $CONTAINER_NAME"
    echo "Port:      $PORT"
    echo "Env File:  $ENV_FILE"
    echo ""
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Bing Grounding MCP Server"
    echo "=========================================="
    echo ""
    
    check_docker
    
    case "${1:-}" in
        --stop)
            stop_container
            log_success "MCP server stopped"
            ;;
        --logs)
            show_logs
            ;;
        --status)
            show_status
            ;;
        --build)
            check_env_file
            build_image
            stop_container
            run_container
            check_health
            ;;
        --help|-h)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  (none)     Build (if needed) and run the MCP server"
            echo "  --build    Force rebuild the Docker image"
            echo "  --stop     Stop the running container"
            echo "  --logs     View container logs (follow mode)"
            echo "  --status   Check server status"
            echo "  --help     Show this help message"
            echo ""
            ;;
        *)
            check_env_file
            
            # Build only if image doesn't exist
            if ! docker images -q "$IMAGE_NAME" | grep -q .; then
                build_image
            else
                log_info "Using existing image: $IMAGE_NAME"
            fi
            
            stop_container
            run_container
            check_health
            
            echo ""
            echo "=========================================="
            echo "  MCP Server is ready!"
            echo "=========================================="
            echo ""
            echo "  URL:      http://localhost:$PORT/mcp"
            echo "  Health:   http://localhost:$PORT/health"
            echo ""
            echo "  To view logs:  $0 --logs"
            echo "  To stop:       $0 --stop"
            echo "  To rebuild:    $0 --build"
            echo ""
            ;;
    esac
}

main "$@"
