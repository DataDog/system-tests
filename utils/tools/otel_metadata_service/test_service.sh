#!/bin/bash
# Quick test script for the OTel PostgreSQL Metadata Service
# Usage: ./test_service.sh [port]

PORT=${1:-8080}
BASE_URL="http://localhost:${PORT}"

echo "🧪 Testing OTel PostgreSQL Metadata Service on ${BASE_URL}"
echo "================================================"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -e "\n${YELLOW}Testing:${NC} ${description}"
    echo "  Endpoint: ${endpoint}"
    
    response=$(curl -s -w "\n%{http_code}" "${BASE_URL}${endpoint}")
    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$status_code" = "200" ]; then
        echo -e "  ${GREEN}✓ Success${NC} (HTTP $status_code)"
        # Show first 100 chars of response
        echo "  Response: $(echo "$body" | head -c 100)..."
    else
        echo -e "  ${RED}✗ Failed${NC} (HTTP $status_code)"
        echo "  Response: $body"
    fi
}

# Wait for service to be ready
echo -e "\n⏳ Checking if service is running..."
max_attempts=5
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s -f "${BASE_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is ready!${NC}"
        break
    fi
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${RED}✗ Service is not responding. Did you start it with 'python main.py'?${NC}"
        echo "  Start the service first: python main.py ${PORT}"
        exit 1
    fi
    echo "  Attempt $attempt/$max_attempts... waiting..."
    sleep 1
done

# Test all endpoints
test_endpoint "/" "Root endpoint"
test_endpoint "/health" "Health check"
test_endpoint "/api/v1/metrics" "Get all metrics"
test_endpoint "/api/v1/metrics/enabled" "Get enabled metrics"
test_endpoint "/api/v1/metrics/postgresql.backends" "Get specific metric"
test_endpoint "/api/v1/resource-attributes" "Get resource attributes"
test_endpoint "/api/v1/attributes" "Get attributes"
test_endpoint "/api/v1/events" "Get events"
test_endpoint "/api/v1/metadata/full" "Get full metadata"

# Test with custom commit SHA
test_endpoint "/api/v1/metrics?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c" "Get metrics with custom commit SHA"

echo -e "\n================================================"
echo -e "${GREEN}✓ All tests completed!${NC}"
echo ""
echo "📚 View interactive docs at: ${BASE_URL}/docs"
echo "📖 View ReDoc at: ${BASE_URL}/redoc"

