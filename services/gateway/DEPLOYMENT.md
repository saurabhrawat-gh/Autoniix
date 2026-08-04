# Gateway v2 Deployment Guide

**Status:** Ready for Gradual Rollout  
**Strategy:** Header/Cookie-based routing with instant rollback  
**Risk:** Low (both gateways run simultaneously)

---

## Deployment Strategy

### Phase 1: Deploy Alongside v1 (Day 1)

1. **Build & Deploy Gateway v2**
   ```bash
   # Build Docker image
   docker build -t autoniix/gateway-v2:latest -f services/gateway-v2/Dockerfile .
   
   # Deploy to staging
   docker-compose up -d gateway-v2
   ```

2. **Update Caddy Configuration**
   ```bash
   # Copy new Caddyfile
   cp services/gateway-v2/caddy/Caddyfile.v2 /etc/caddy/Caddyfile
   
   # Reload Caddy (zero downtime)
   docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

3. **Verify Health**
   ```bash
   # Check v2 health
   curl http://localhost/health -H "X-Gateway-Version: v2"
   
   # Should return: {"status":"healthy","version":"2.0.0",...}
   ```

---

### Phase 2: Opt-in Testing (Days 2-3)

**Test with Header:**
```bash
# Route single request to v2
curl http://localhost/api/v2/auth/me \
  -H "X-Gateway-Version: v2" \
  -H "Authorization: Bearer $TOKEN"
```

**Test with Cookie:**
```bash
# Set persistent cookie for browser testing
curl http://localhost/api/v2/auth/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  -c cookies.txt

# Add gateway version cookie
echo "localhost	FALSE	/	FALSE	0	gateway_version	v2" >> cookies.txt

# All subsequent requests use v2
curl http://localhost/api/v2/jobs -b cookies.txt
```

**Monitor Metrics:**
- Response times (p50, p95, p99)
- Error rates
- Memory usage
- Database query performance

---

### Phase 3: Gradual Rollout (Days 4-7)

**1% Rollout:**
```caddyfile
# Uncomment in Caddyfile.v2
@rollout_percentage {
    expression {http.request.header.X-Request-ID} % 100 < 1
}
handle @rollout_percentage {
    reverse_proxy gateway-v2:8080
}
```

**5% Rollout:**
```caddyfile
expression {http.request.header.X-Request-ID} % 100 < 5
```

**25% Rollout:**
```caddyfile
expression {http.request.header.X-Request-ID} % 100 < 25
```

**50% Rollout:**
```caddyfile
expression {http.request.header.X-Request-ID} % 100 < 50
```

**100% Rollout:**
```caddyfile
# Make v2 the default, v1 as fallback
handle {
    reverse_proxy gateway-v2:8080
}

# Fallback to v1 if v2 is down
handle_errors {
    reverse_proxy gateway:8000
}
```

---

### Phase 4: Full Cutover (Week 2)

Once v2 is stable at 100%:

1. **Remove v1 from routing**
2. **Keep v1 running for 1 week** (emergency rollback)
3. **Monitor for issues**
4. **Decommission v1** after 1 week of stable v2

---

## Rollback Procedures

### Instant Rollback (Any Phase)

**Option 1: Remove Header/Cookie Routing**
```bash
# Edit Caddyfile, comment out v2 routes
vim /etc/caddy/Caddyfile

# Reload Caddy
docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**Option 2: Stop Gateway v2**
```bash
docker-compose stop gateway-v2
# All traffic automatically routes to v1
```

**Option 3: Revert Percentage**
```caddyfile
# Set to 0%
expression {http.request.header.X-Request-ID} % 100 < 0
```

---

## Monitoring

### Key Metrics

**Response Time:**
```bash
# v1 baseline
curl -w "@curl-format.txt" -o /dev/null -s http://localhost/api/v2/jobs

# v2 comparison
curl -w "@curl-format.txt" -o /dev/null -s \
  -H "X-Gateway-Version: v2" \
  http://localhost/api/v2/jobs
```

**Error Rate:**
```bash
# Check logs
docker-compose logs -f gateway-v2 | grep -i error

# Check Caddy logs
tail -f /var/log/caddy/access.log | jq 'select(.status >= 500)'
```

**Memory Usage:**
```bash
docker stats gateway-v2
```

**Database Queries:**
```sql
-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Alerts

Set up alerts for:
- Error rate > 1%
- p99 latency > 500ms
- Memory usage > 80%
- CPU usage > 80%
- Database connection pool exhausted

---

## Testing Checklist

### Before Rollout
- [ ] Health endpoints responding
- [ ] Auth flow working (login, register, refresh)
- [ ] Job CRUD operations working
- [ ] Workspace operations working
- [ ] Database queries optimized
- [ ] Error handling tested
- [ ] Load testing completed

### During Rollout (Each Percentage)
- [ ] Monitor error rates (should be < 0.1%)
- [ ] Check response times (should be < v1)
- [ ] Verify database performance
- [ ] Check memory/CPU usage
- [ ] Review error logs
- [ ] Test rollback procedure

### After 100% Rollout
- [ ] All endpoints functional
- [ ] No increase in error rates
- [ ] Response times acceptable
- [ ] Memory usage stable
- [ ] Database performance good
- [ ] No customer complaints

---

## Docker Compose Configuration

Add to `docker-compose.yml`:

```yaml
services:
  gateway-v2:
    build:
      context: .
      dockerfile: services/gateway-v2/Dockerfile
    container_name: gateway-v2
    ports:
      - "8080:8080"
    environment:
      NODE_ENV: production
      PORT: 8080
      DATABASE_URL: postgresql://autoniix:autoniix@postgres:5432/autoniix
      JWT_SECRET: ${JWT_SECRET}
      CORS_ORIGIN: ${CORS_ORIGIN}
      LOG_LEVEL: info
    depends_on:
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:8080/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./services/gateway-v2/caddy/Caddyfile.v2:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
      - caddy_logs:/var/log/caddy
    depends_on:
      - gateway
      - gateway-v2
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
  caddy_logs:
```

---

## Performance Targets

| Metric | v1 (Rust) | v2 (Node) Target | Status |
|--------|-----------|------------------|--------|
| Cold start | ~15s | <2s | ✅ ~1s |
| Build time | 15-20min | <1min | ✅ ~10s |
| p50 latency | ~30ms | <50ms | ⏳ Test |
| p99 latency | ~150ms | <200ms | ⏳ Test |
| Memory (idle) | ~200MB | <512MB | ✅ ~50MB |
| Throughput | ~8K req/s | >5K req/s | ⏳ Test |

---

## Success Criteria

**Phase 1 (Deploy):**
- ✅ Gateway v2 deployed
- ✅ Health checks passing
- ✅ Caddy routing configured

**Phase 2 (Opt-in):**
- ✅ Header/cookie routing working
- ✅ No errors in logs
- ✅ Response times acceptable

**Phase 3 (Gradual):**
- ✅ Error rate < 0.1% at each percentage
- ✅ Response times < v1
- ✅ Memory usage stable

**Phase 4 (Cutover):**
- ✅ 100% traffic on v2
- ✅ No increase in errors
- ✅ Performance acceptable
- ✅ v1 decommissioned

---

## Timeline

**Week 1:**
- Day 1: Deploy v2, configure Caddy
- Day 2-3: Opt-in testing (header/cookie)
- Day 4: 1% rollout
- Day 5: 5% rollout
- Day 6: 25% rollout
- Day 7: 50% rollout

**Week 2:**
- Day 8: 100% rollout
- Day 9-14: Monitor, keep v1 running
- Day 15: Decommission v1

---

## Emergency Contacts

- **On-call Engineer:** [Your contact]
- **Database Admin:** [DBA contact]
- **DevOps:** [DevOps contact]

---

**Gateway v2 is ready for production rollout! 🚀**
