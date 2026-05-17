#!/usr/bin/env bash
# scripts/check-stack.sh — verify every part of the youtube-automation stack
# Usage:
#   bash scripts/check-stack.sh         → run full health check, exit 0/1
#   bash scripts/check-stack.sh wait    → wait up to 90s for all healthchecks to go green
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; FAILED=1; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }

FAILED=0
MODE="${1:-check}"

# Required containers (compose service names without project prefix)
REQUIRED_SERVICES=(
  postgres-app postgres-temporal redis temporal temporal-ui minio
  research script voice assets thumbnail assembly delivery analytics
  admin direction brand editor sheets-sync
  remotion-api remotion-worker
  worker-production worker-scheduler
  dashboard-bff dashboard-ui
)

# HTTP endpoints to verify (URL → friendly name)
declare -A HTTP_ENDPOINTS=(
  ["http://localhost:8020/health"]="dashboard-bff"
  ["http://localhost:3000"]="dashboard-ui"
  ["http://localhost:8080"]="temporal-ui"
)

# 1. Wait mode: poll docker compose ps for healthy status
if [[ "$MODE" == "wait" ]]; then
  for i in {1..45}; do
    NOT_READY=0
    for svc in "${REQUIRED_SERVICES[@]}"; do
      STATUS=$(docker compose ps --format '{{.Service}} {{.Status}}' 2>/dev/null | awk -v s="$svc" '$1==s {$1=""; print}')
      if [[ -z "$STATUS" ]]; then NOT_READY=$((NOT_READY+1)); continue; fi
      if [[ "$STATUS" != *"Up"* ]] || [[ "$STATUS" == *"unhealthy"* ]] || [[ "$STATUS" == *"health: starting"* ]]; then
        NOT_READY=$((NOT_READY+1))
      fi
    done
    if [[ $NOT_READY -eq 0 ]]; then echo "✅ All services healthy"; exit 0; fi
    sleep 2
  done
  echo "⚠️  Some services still not healthy after 90s — running full report below"
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  YouTube Automation — Stack Health Check"
echo "═══════════════════════════════════════════════════"
echo ""

# 2. Container status
echo "📦  Containers (${#REQUIRED_SERVICES[@]} expected):"
PS_OUTPUT=$(docker compose ps --format '{{.Service}}|{{.Status}}' 2>/dev/null)
for svc in "${REQUIRED_SERVICES[@]}"; do
  LINE=$(echo "$PS_OUTPUT" | awk -F'|' -v s="$svc" '$1==s {print $2}')
  if [[ -z "$LINE" ]]; then
    fail "$svc — NOT RUNNING"
  elif [[ "$LINE" == *"unhealthy"* ]]; then
    fail "$svc — unhealthy"
  elif [[ "$LINE" == *"Up"* ]]; then
    ok "$svc — $LINE"
  else
    fail "$svc — $LINE"
  fi
done
echo ""

# 3. HTTP endpoints
echo "🌐  HTTP endpoints:"
for url in "${!HTTP_ENDPOINTS[@]}"; do
  name="${HTTP_ENDPOINTS[$url]}"
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo "000")
  if [[ "$CODE" =~ ^(200|301|302|404)$ ]]; then
    ok "$name ($url) → $CODE"
  else
    fail "$name ($url) → $CODE"
  fi
done
echo ""

# 4. Database sanity
echo "🗄️   Database:"
CHANNEL_COUNT=$(docker compose exec -T postgres-app sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc "SELECT COUNT(*) FROM channels"' 2>/dev/null | tr -d '[:space:]')
if [[ "$CHANNEL_COUNT" =~ ^[0-9]+$ ]]; then
  ok "channels table reachable — $CHANNEL_COUNT rows"
else
  fail "channels table unreachable"
fi
ACTIVE_VIDEOS=$(docker compose exec -T postgres-app sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc "SELECT COUNT(*) FROM videos WHERE status NOT IN (\"delivered\",\"test_delivered\",\"failed\",\"rejected\")"' 2>/dev/null | tr -d '[:space:]')
if [[ "$ACTIVE_VIDEOS" =~ ^[0-9]+$ ]]; then
  ok "videos table reachable — $ACTIVE_VIDEOS in-progress"
fi
echo ""

# 5. Temporal namespace
echo "⚙️   Temporal:"
NS=$(docker compose exec -T temporal tctl --address temporal:7233 namespace list 2>/dev/null | grep -c "^Name: default")
if [[ "$NS" -ge 1 ]]; then
  ok "default namespace registered"
else
  fail "default namespace MISSING — run: docker compose exec temporal tctl --namespace default namespace register --retention 7"
fi
echo ""

# 6. Auth smoke test
echo "🔐  Auth smoke test:"
TOKEN=$(curl -s -X POST http://localhost:8020/api/auth/login \
  -H 'Content-Type: application/json' -d '{"password":"admin"}' \
  --max-time 5 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("token",""))' 2>/dev/null)
if [[ -n "$TOKEN" ]]; then
  ok "POST /api/auth/login returned token"
  CHCOUNT=$(curl -s http://localhost:8020/api/channels -H "Authorization: Bearer $TOKEN" --max-time 5 \
    | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("data",[])))' 2>/dev/null)
  if [[ "$CHCOUNT" =~ ^[0-9]+$ ]]; then
    ok "GET /api/channels returned $CHCOUNT channels"
  else
    fail "GET /api/channels failed"
  fi
else
  fail "POST /api/auth/login failed"
fi
echo ""

# 7. Final summary
echo "═══════════════════════════════════════════════════"
if [[ $FAILED -eq 0 ]]; then
  echo -e "  ${GREEN}✓ Stack is fully healthy${NC}"
  echo "  Dashboard: http://localhost:3000  (login: admin)"
  echo "  Temporal:  http://localhost:8080"
else
  echo -e "  ${RED}✗ Stack has issues — see above${NC}"
fi
echo "═══════════════════════════════════════════════════"
exit $FAILED
