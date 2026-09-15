#!/bin/bash
set -e

echo "=========================================="
echo "Autoniix Manual Testing Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo "Step 1: Checking if services are running..."
echo "-----------------------------------"

if ! docker compose ps | grep -q "Up"; then
    echo -e "${YELLOW}Services not running. Starting services...${NC}"
    make up
else
    echo -e "${GREEN}✓ Services already running${NC}"
fi

echo ""

# Wait for services to be healthy
echo "Step 2: Waiting for services to be healthy..."
echo "-----------------------------------"

max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if make health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ All services healthy${NC}"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "Waiting for services... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ Services failed to become healthy${NC}"
    echo "Run 'docker compose logs' to see what went wrong"
    exit 1
fi

echo ""

# Run database migrations
echo "Step 3: Running database migrations..."
echo "-----------------------------------"

if make migrate > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Migrations applied${NC}"
else
    echo -e "${YELLOW}⚠ Migrations may have already been applied${NC}"
fi

echo ""

# Create test channel
echo "Step 4: Creating test channel..."
echo "-----------------------------------"

docker compose exec -T postgres-app psql -U autoniix -d autoniix_app <<EOF
INSERT INTO channels (
    channel_id, 
    channel_name, 
    niche, 
    target_audience,
    content_mode,
    voice_id,
    created_at
) VALUES (
    'test_channel_001',
    'Test Channel',
    'technology',
    'tech enthusiasts',
    'short',
    'inworld-default',
    NOW()
) ON CONFLICT (channel_id) DO UPDATE SET
    updated_at = NOW();
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test channel created/updated${NC}"
else
    echo -e "${RED}✗ Failed to create test channel${NC}"
    exit 1
fi

echo ""

# Display service URLs
echo "Step 5: Service URLs"
echo "-----------------------------------"
echo "Gateway:        http://localhost:8000"
echo "Research:       http://localhost:8001"
echo "Script:         http://localhost:8002"
echo "Voice:          http://localhost:8003"
echo "Assets:         http://localhost:8004"
echo "Thumbnail:      http://localhost:8005"
echo "Assembly:       http://localhost:8006"
echo "Delivery:       http://localhost:8007"
echo "Direction:      http://localhost:8008"
echo "Streaming Hub:  http://localhost:8009"
echo ""

# Display Postman instructions
echo "Step 6: Postman Setup"
echo "-----------------------------------"
echo "1. Import collection:"
echo "   File: Autoniix_Pipeline_Tests.postman_collection.json"
echo ""
echo "2. Import environment (or create manually):"
echo "   - gateway_url: http://localhost:8000"
echo "   - research_url: http://localhost:8001"
echo "   - channel_id: test_channel_001"
echo ""
echo "3. Start testing:"
echo "   - Run 'Phase 0: Health Checks' to verify all services"
echo "   - Run 'Phase 1: Authentication' to get auth token"
echo "   - Run 'Phase 2: Research Service' to test T3.1"
echo "   - Run 'Phase 11: End-to-End Pipeline' for full test"
echo ""

# Display testing guide
echo "Step 7: Testing Guide"
echo "-----------------------------------"
echo "Full testing guide: MANUAL_TESTING_GUIDE.md"
echo ""
echo "Quick test commands:"
echo "  make health          - Check all services"
echo "  make logs            - View all logs"
echo "  make logs-svc SVC=research - View specific service logs"
echo ""

# Display next steps
echo "=========================================="
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Open Postman"
echo "2. Import Autoniix_Pipeline_Tests.postman_collection.json"
echo "3. Run Phase 0 (Health Checks) to verify everything works"
echo "4. Run Phase 1 (Authentication) to get auth token"
echo "5. Run Phase 2 (Research Service) to test Tier 3.1"
echo ""
echo "For detailed testing instructions, see:"
echo "  MANUAL_TESTING_GUIDE.md"
echo ""
