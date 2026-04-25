# Security & Compliance

> Secrets management, network security, authentication, RBAC, YouTube policy, audit logging, and prompt injection prevention.

---

## Security Architecture

```
Internet
  │
  ▼
┌──────────────────────────┐
│  Traefik (API Gateway)    │  TLS termination, HSTS, rate limiting
│  Port 443 only            │  Let's Encrypt auto-renewal
└────────────┬─────────────┘
             │ HTTPS only
    ┌────────┼─────────┐
    │        │         │
    ▼        ▼         ▼
 Admin    Temporal   Webhook
  API       UI      Endpoints
 (JWT)   (Basic     (HMAC
          Auth)    signature)
    │        │         │
    └────────┼─────────┘
             │
    Docker Internal Network (yt-net)
    ─────────────────────────────────
    All services: private, no public ports
    Communication: HTTP over Docker DNS
    Secrets: Docker secrets / env vars
```

---

## Secrets Management

### Phase 1: Docker Secrets + .env (Current)

```bash
# .env (git-ignored, never committed)
DB_PASSWORD=<strong-random>
REDIS_URL=redis://redis:6379
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=AIza...
FISH_AUDIO_API_KEY=...
SERPAPI_KEY=...
PIXABAY_API_KEY=...
YOUTUBE_API_KEY=AIza...
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
ADMIN_JWT_SECRET=<64-char-random>
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...
```

Docker Compose loads from `.env`:
```yaml
services:
  research:
    env_file: .env
    # OR use Docker secrets for sensitive values:
    secrets:
      - openai_key
      - anthropic_key

secrets:
  openai_key:
    file: ./secrets/openai_key.txt
  anthropic_key:
    file: ./secrets/anthropic_key.txt
```

### Phase 2: HashiCorp Vault (Roadmap, 25+ channels)

- Dynamic secrets with TTL
- Auto-rotation of API keys
- Audit trail for secret access
- Services authenticate via Vault AppRole

### Rules

1. **Never** store secrets in code, docs, or git history
2. **Never** log secret values (mask in structured logs)
3. Rotate API keys every 90 days (calendar reminder)
4. Use least-privilege: each service gets only the keys it needs

---

## Network Security

### Docker Network Isolation

```yaml
networks:
  yt-net:
    driver: bridge
    internal: false  # Traefik needs internet access

  yt-internal:
    driver: bridge
    internal: true   # No internet access for DB, Redis, MinIO
```

| Service | Network | Public Port | Notes |
|---------|---------|------------|-------|
| Traefik | yt-net | 443, 80 | Only public-facing service |
| Admin API | yt-net | — (via Traefik) | JWT-protected |
| Temporal UI | yt-net | — (via Traefik) | Basic auth or JWT |
| All other services | yt-internal | None | Private only |
| PostgreSQL | yt-internal | None | Never exposed |
| Redis | yt-internal | None | Never exposed |
| MinIO | yt-internal | None | Console via Traefik if needed |

### Traefik Configuration

```yaml
# traefik.yml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@yourdomain.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

# Security headers
http:
  middlewares:
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        contentTypeNosniff: true
        frameDeny: true
        browserXssFilter: true

    rate-limit:
      rateLimit:
        average: 100
        burst: 50
        period: 1m
```

### Firewall Rules (VPS level)

```bash
# Allow only necessary ports
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH (consider changing port)
ufw allow 80/tcp    # HTTP (redirects to HTTPS)
ufw allow 443/tcp   # HTTPS
ufw enable

# If using WireGuard VPN between VPSes
ufw allow 51820/udp
ufw allow from 10.0.0.0/24  # VPN subnet
```

---

## Authentication & Authorization

### Service-to-Service (Internal)

Phase 1 (current): Services trust each other on the Docker internal network. No auth between internal services.

Phase 2 (10+ channels): Add JWT validation on each service:
```python
# middleware for internal services
from fastapi import Depends, HTTPException
from jose import jwt

async def verify_internal_token(authorization: str = Header(...)):
    try:
        payload = jwt.decode(authorization.replace("Bearer ", ""), INTERNAL_SECRET, algorithms=["HS256"])
        if payload.get("iss") != "temporal-worker":
            raise HTTPException(403, "Invalid issuer")
    except Exception:
        raise HTTPException(401, "Invalid token")
```

Phase 3 (50+ channels): mTLS between services (certificates managed by Vault).

### Admin API Authentication

```python
# JWT-based auth with RBAC
from fastapi import Depends, HTTPException
from jose import jwt

ROLES = {
    "admin": ["*"],                    # Full access
    "operator": ["channels.*", "system.pause", "system.resume", "videos.read"],
    "viewer": ["channels.read", "videos.read", "costs.read", "audit.read"],
}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=["HS256"])
    return User(
        email=payload["sub"],
        role=payload["role"],
        permissions=ROLES[payload["role"]],
    )

def require_permission(permission: str):
    async def checker(user: User = Depends(get_current_user)):
        if "*" not in user.permissions and permission not in user.permissions:
            raise HTTPException(403, f"Missing permission: {permission}")
        return user
    return checker

# Usage
@router.post("/system/emergency-stop")
async def emergency_stop(user: User = Depends(require_permission("system.emergency_stop"))):
    ...
```

### Webhook Authentication (Temporal → External)

For callbacks to external systems (e.g., notification webhooks):
```python
import hmac, hashlib

def sign_webhook(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

# Verify incoming webhook
def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## Audit Logging

Every significant action is logged to the `audit_log` table:

```python
async def audit(actor: str, action: str, resource_type: str, resource_id: str, details: dict = None):
    await db.execute(
        "INSERT INTO audit_log (actor, action, resource_type, resource_id, details) "
        "VALUES ($1, $2, $3, $4, $5)",
        actor, action, resource_type, resource_id, json.dumps(details),
    )
```

### Audited Actions

| Action | Actor | Resource |
|--------|-------|----------|
| Channel created/updated/disabled | admin:email | channel:id |
| System paused/resumed/emergency-stopped | admin:email | system |
| Config changed | admin:email | config:key |
| Video production started | workflow:id | video:id |
| Video approved/rejected (human review) | admin:email | video:id |
| Budget threshold reached | system | budget |
| Provider circuit opened | system | provider:name |
| Secret rotated | admin:email | secret:name |

### Retention

- Keep audit logs for 365 days minimum
- Export to MinIO monthly for long-term storage
- Never delete audit logs (append-only)

---

## Input Validation & Prompt Injection Prevention

### Pydantic Validation at Every Service Boundary

```python
from pydantic import BaseModel, validator, constr
import re

class SceneInput(BaseModel):
    id: constr(pattern=r'^s\d+$', max_length=10)
    text_raw: constr(max_length=5000)
    emotion: str | None
    
    @validator('text_raw')
    def sanitize_text(cls, v):
        # Remove potential prompt injection patterns
        v = re.sub(r'(?i)(ignore previous|disregard|forget|override|system prompt)', '[FILTERED]', v)
        # Remove control characters
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)
        return v
    
    @validator('emotion')
    def validate_emotion(cls, v):
        allowed = {'curious', 'serious', 'excited', 'dramatic', 'calm', 'urgent', 'informative', None}
        if v not in allowed:
            raise ValueError(f'Invalid emotion: {v}')
        return v
```

### LLM Prompt Safety

```python
def build_safe_prompt(template: str, user_data: dict) -> str:
    """Inject user data into prompt with safety boundaries."""
    # Wrap user data in clear delimiters
    safe_data = {}
    for key, value in user_data.items():
        # Sanitize
        value = str(value)
        value = re.sub(r'(?i)(ignore|disregard|forget|override|system)', '[FILTERED]', value)
        value = value[:10000]  # Truncate
        safe_data[key] = value
    
    return template.format(**safe_data)
```

### Database Input Safety

- All queries use parameterized statements (SQLAlchemy / asyncpg)
- No string concatenation in SQL
- JSONB fields validated via Pydantic before insertion
- Content from external APIs (YouTube, SerpAPI) sanitized before storage

---

## YouTube Policy Compliance

### Automated Compliance Checks (Assembly Service)

| Check | Rule | Action |
|-------|------|--------|
| AI disclosure | Always required for AI-generated content | Auto-injected in description + YouTube API flag |
| Health disclaimer | Required for health niche | Auto-injected: "For educational purposes only. Consult a healthcare professional." |
| Finance disclaimer | Required for finance niche | Auto-injected: "This is not financial advice." |
| Made for kids | Never (our content targets adults) | Set `madeForKids: false` in API |
| Violent/graphic content | Detect in script text | Block if detected |
| Misleading claims | Fact confidence < 0.7 | Remove claim from script |
| Clickbait | Authenticity score < 8.0 | Block title/thumbnail |
| Copyright | Stock footage license check | Only free/CC assets |

### Cross-Channel Safety (at Scale)

| Risk | Mitigation |
|------|-----------|
| YouTube linking channels as spam ring | Different voice per channel, different templates, stagger uploads |
| Content fingerprint similarity | Cross-channel dedup gate (< 40% similarity) |
| Upload velocity triggers | Max 2 uploads/day/channel, natural scheduling |
| Community guideline strikes | Policy scanner, conservative thresholds, human review for edge cases |

### Brand Account Structure

```
Management Account: yt.empire.management@gmail.com
  └─ Brand Account 1: Body Signals (5 channels)
  └─ Brand Account 2: Money Decoded (3 channels)
  └─ Brand Account 3: Mind Shifts (2 channels)
  └─ ... (up to 100 channels per management account)

AdSense: saurabhrawat.official@gmail.com
  └─ Linked to ALL channels (ONE account)

For 100+ channels:
  └─ Additional management account
  └─ Same AdSense linked
```

---

## Data Privacy

### What Data We Store

| Data Type | Storage | Retention | PII Risk |
|-----------|---------|-----------|----------|
| Channel config | PostgreSQL | Indefinite | Low (no user PII) |
| Generated scripts | MinIO | 90 days | None |
| Audio files | MinIO | 90 days | None (AI voice) |
| Video files | MinIO | 30 days (then YouTube only) | None |
| API usage logs | PostgreSQL | 365 days | None |
| Audit logs | PostgreSQL | 365 days | Contains admin emails |
| YouTube analytics | PostgreSQL | 365 days | None (aggregate data) |

### GDPR Considerations

- No end-user PII is collected or processed
- Admin user data (email, role) is minimal and functional
- Audit logs with admin emails: retained for accountability
- Right to erasure: Admin accounts can be anonymized in audit logs

---

## Security Checklist (Pre-Launch)

- [ ] All secrets in `.env` (not in code or docs)
- [ ] `.env` in `.gitignore`
- [ ] Traefik TLS configured with Let's Encrypt
- [ ] HTTP → HTTPS redirect enabled
- [ ] HSTS headers configured
- [ ] SSH key-only auth (disable password login)
- [ ] SSH port changed from 22
- [ ] UFW firewall enabled (only 80, 443, SSH)
- [ ] Docker services on internal network
- [ ] PostgreSQL not publicly exposed
- [ ] Redis not publicly exposed (no AUTH needed on internal network)
- [ ] MinIO not publicly exposed
- [ ] Admin API behind JWT
- [ ] Temporal UI behind basic auth or JWT
- [ ] Audit logging active
- [ ] Daily PostgreSQL backups configured
- [ ] Monitoring alerts for: disk space, memory, error rate
- [ ] API key rotation calendar set (90-day cycle)
