#!/bin/bash
set -e

# Video Production Pipeline End-to-End Test
# Tests all 11 phases of the video production workflow

echo "=========================================="
echo "Video Production Pipeline E2E Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
TEMPORAL_UI="${TEMPORAL_UI:-http://localhost:8233}"
TEST_CHANNEL_ID="${TEST_CHANNEL_ID:-test_channel_001}"
CONTENT_MODE="${CONTENT_MODE:-short}"

echo "Configuration:"
echo "  Gateway URL: $GATEWAY_URL"
echo "  Temporal UI: $TEMPORAL_UI"
echo "  Channel ID: $TEST_CHANNEL_ID"
echo "  Content Mode: $CONTENT_MODE"
echo ""

# Function to check service health
check_service() {
    local service_name=$1
    local health_url=$2
    
    echo -n "Checking $service_name... "
    if curl -s -f "$health_url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Step 1: Check all services are running
echo "Step 1: Checking service health..."
echo "-----------------------------------"

SERVICES_OK=true

check_service "Gateway" "$GATEWAY_URL/health" || SERVICES_OK=false
check_service "Research" "http://localhost:8001/health" || SERVICES_OK=false
check_service "Script" "http://localhost:8002/health" || SERVICES_OK=false
check_service "Voice" "http://localhost:8003/health" || SERVICES_OK=false
check_service "Assets" "http://localhost:8004/health" || SERVICES_OK=false
check_service "Thumbnail" "http://localhost:8005/health" || SERVICES_OK=false
check_service "Assembly" "http://localhost:8006/health" || SERVICES_OK=false
check_service "Delivery" "http://localhost:8007/health" || SERVICES_OK=false
check_service "Direction" "http://localhost:8008/health" || SERVICES_OK=false

echo ""

if [ "$SERVICES_OK" = false ]; then
    echo -e "${RED}ERROR: Some services are not healthy. Please start all services with 'make dev'${NC}"
    exit 1
fi

echo -e "${GREEN}All services healthy!${NC}"
echo ""

# Step 2: Create test channel if it doesn't exist
echo "Step 2: Ensuring test channel exists..."
echo "----------------------------------------"

CHANNEL_PAYLOAD='{
  "channel_id": "'$TEST_CHANNEL_ID'",
  "name": "Test Channel",
  "niche": "health",
  "brand_voice": "informative and engaging",
  "content_mode": "'$CONTENT_MODE'",
  "short_form_duration": 45,
  "long_form_duration": 480,
  "words_per_video_short": 80,
  "words_per_video_long": 1100
}'

curl -s -X POST "$GATEWAY_URL/api/channels" \
  -H "Content-Type: application/json" \
  -d "$CHANNEL_PAYLOAD" > /dev/null 2>&1 || true

echo -e "${GREEN}Channel ready${NC}"
echo ""

# Step 3: Trigger video production
echo "Step 3: Triggering video production..."
echo "---------------------------------------"

JOB_PAYLOAD='{
  "channel_id": "'$TEST_CHANNEL_ID'",
  "content_mode": "'$CONTENT_MODE'",
  "topic_candidates": ["5 Signs Your Body Needs More Sleep"],
  "environment": "test",
  "max_cost_usd": 5.0
}'

echo "Payload:"
echo "$JOB_PAYLOAD" | jq '.'
echo ""

RESPONSE=$(curl -s -X POST "$GATEWAY_URL/api/jobs/create" \
  -H "Content-Type: application/json" \
  -d "$JOB_PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq '.'
echo ""

# Extract workflow ID and content ID
WORKFLOW_ID=$(echo "$RESPONSE" | jq -r '.data.workflow_id // empty')
CONTENT_ID=$(echo "$RESPONSE" | jq -r '.data.content_id // empty')

if [ -z "$WORKFLOW_ID" ] || [ -z "$CONTENT_ID" ]; then
    echo -e "${RED}ERROR: Failed to start workflow${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi

echo -e "${GREEN}Workflow started!${NC}"
echo "  Workflow ID: $WORKFLOW_ID"
echo "  Content ID: $CONTENT_ID"
echo "  Temporal UI: $TEMPORAL_UI/namespaces/default/workflows/$WORKFLOW_ID"
echo ""

# Step 4: Monitor workflow progress
echo "Step 4: Monitoring workflow progress..."
echo "---------------------------------------"
echo ""

PHASES=(
    "researching"
    "scripting"
    "voice_synthesis"
    "asset_gathering"
    "thumbnail_generation"
    "direction_generation"
    "rendering"
    "finishing"
    "delivery"
    "analytics"
)

CURRENT_PHASE=""
PHASE_INDEX=0
MAX_WAIT=600  # 10 minutes max
ELAPSED=0
POLL_INTERVAL=5

echo "Expected phases: ${PHASES[@]}"
echo ""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Query workflow status
    STATUS_RESPONSE=$(curl -s "$GATEWAY_URL/api/jobs/$CONTENT_ID/status" || echo '{}')
    
    PHASE=$(echo "$STATUS_RESPONSE" | jq -r '.data.phase // "unknown"')
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.data.status // "unknown"')
    COST=$(echo "$STATUS_RESPONSE" | jq -r '.data.accrued_cost // 0')
    
    # Check if phase changed
    if [ "$PHASE" != "$CURRENT_PHASE" ]; then
        if [ -n "$CURRENT_PHASE" ]; then
            echo -e "${GREEN}✓${NC} $CURRENT_PHASE completed"
        fi
        CURRENT_PHASE="$PHASE"
        echo -n "→ $CURRENT_PHASE... "
    fi
    
    # Check if workflow completed
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "delivered" ]; then
        echo -e "${GREEN}✓${NC}"
        echo ""
        echo -e "${GREEN}Workflow completed successfully!${NC}"
        echo "  Final phase: $PHASE"
        echo "  Total cost: \$$COST"
        break
    fi
    
    # Check if workflow failed
    if [ "$STATUS" = "failed" ] || [ "$STATUS" = "blocked_quality_gate" ]; then
        echo -e "${RED}✗${NC}"
        echo ""
        echo -e "${RED}Workflow failed!${NC}"
        echo "  Phase: $PHASE"
        echo "  Status: $STATUS"
        echo "  Response: $STATUS_RESPONSE"
        exit 1
    fi
    
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
    
    # Show progress indicator
    echo -n "."
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo -e "${YELLOW}WARNING: Workflow still running after ${MAX_WAIT}s${NC}"
    echo "  Current phase: $CURRENT_PHASE"
    echo "  Check Temporal UI for details: $TEMPORAL_UI/namespaces/default/workflows/$WORKFLOW_ID"
fi

echo ""

# Step 5: Verify video output
echo "Step 5: Verifying video output..."
echo "----------------------------------"

VIDEO_RESPONSE=$(curl -s "$GATEWAY_URL/api/videos/$CONTENT_ID" || echo '{}')

VIDEO_URL=$(echo "$VIDEO_RESPONSE" | jq -r '.data.rendered_video_url // empty')
YOUTUBE_ID=$(echo "$VIDEO_RESPONSE" | jq -r '.data.youtube_video_id // empty')
FINAL_SCORE=$(echo "$VIDEO_RESPONSE" | jq -r '.data.final_composite_score // 0')

echo "Video Details:"
echo "  Content ID: $CONTENT_ID"
echo "  Video URL: ${VIDEO_URL:-'(not rendered)'}"
echo "  YouTube ID: ${YOUTUBE_ID:-'(not uploaded)'}"
echo "  Final Score: $FINAL_SCORE"
echo ""

if [ -n "$VIDEO_URL" ]; then
    echo -e "${GREEN}✓ Video rendered successfully${NC}"
    echo "  Download: $VIDEO_URL"
else
    echo -e "${YELLOW}⚠ Video not rendered (may still be processing)${NC}"
fi

echo ""

# Step 6: Validation checks
echo "Step 6: Running validation checks..."
echo "-------------------------------------"

VALIDATION_OK=true

# Check 1: Timeline sync
echo -n "Checking timeline sync... "
SYNC_VALIDATION=$(echo "$VIDEO_RESPONSE" | jq -r '.data.sync_validation.passed // false')
if [ "$SYNC_VALIDATION" = "true" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
    SYNC_ISSUES=$(echo "$VIDEO_RESPONSE" | jq -r '.data.sync_validation.issues // []')
    echo "  Issues: $SYNC_ISSUES"
    VALIDATION_OK=false
fi

# Check 2: Quality scores
echo -n "Checking quality scores... "
if (( $(echo "$FINAL_SCORE >= 7.0" | bc -l) )); then
    echo -e "${GREEN}✓${NC} (score: $FINAL_SCORE)"
else
    echo -e "${YELLOW}⚠${NC} (score: $FINAL_SCORE, expected >= 7.0)"
    VALIDATION_OK=false
fi

# Check 3: All phases completed
echo -n "Checking phase completion... "
COMPLETED_PHASES=$(echo "$VIDEO_RESPONSE" | jq -r '.data.completed_phases // [] | length')
EXPECTED_PHASES=11
if [ "$COMPLETED_PHASES" -eq "$EXPECTED_PHASES" ]; then
    echo -e "${GREEN}✓${NC} ($COMPLETED_PHASES/$EXPECTED_PHASES)"
else
    echo -e "${YELLOW}⚠${NC} ($COMPLETED_PHASES/$EXPECTED_PHASES)"
    VALIDATION_OK=false
fi

echo ""

# Final summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""

if [ "$VALIDATION_OK" = true ] && [ -n "$VIDEO_URL" ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo ""
    echo "The video production pipeline is working end-to-end!"
    echo ""
    echo "Next steps:"
    echo "  1. Download and review the video: $VIDEO_URL"
    echo "  2. Check video quality (timeline, audio sync, transitions)"
    echo "  3. If quality is good, deploy to production"
    exit 0
else
    echo -e "${YELLOW}⚠ SOME CHECKS FAILED${NC}"
    echo ""
    echo "Please review the warnings above and check:"
    echo "  1. Temporal workflow logs"
    echo "  2. Service logs (docker-compose logs)"
    echo "  3. Video output quality"
    exit 1
fi
