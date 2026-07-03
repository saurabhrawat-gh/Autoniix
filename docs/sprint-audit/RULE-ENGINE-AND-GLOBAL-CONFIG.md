# Rule Engine & Global Configuration System

> **Single source of truth for every permission, role, feature flag, system config, and access rule.**
> Every sprint references this document for authorization and configuration decisions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    REQUEST FLOW                                  │
│                                                                  │
│  User Request ──→ principal_dep ──→ Principal                   │
│                      │                                           │
│                      ├──→ require_role(*roles)                   │
│                      ├──→ require_global_role(*roles)            │
│                      ├──→ require_permission(perm)               │
│                      └──→ flag_enabled(key)                      │
│                                                                  │
│  Principal { user_id, email, role, global_role, workspace_id }   │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              RULE ENGINE (to be built)                    │   │
│  │                                                          │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Role     │  │ Permission   │  │ Feature Flags    │   │   │
│  │  │ Matrix   │  │ Matrix       │  │ (runtime toggles)│   │   │
│  │  └──────────┘  └──────────────┘  └──────────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Section  │  │ Feature-Level│  │ System Config    │   │   │
│  │  │Visibility│  │ Access Rules │  │ (key-value)      │   │   │
│  │  └──────────┘  └──────────────┘  └──────────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Scope    │  │ Quota        │  │ Audit Trail      │   │   │
│  │  │ Resolver │  │ Enforcer     │  │ (immutable)      │   │   │
│  │  └──────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Role System

### 1.1 Role Hierarchy

```
                    ┌──────────────┐
                    │  SUPERADMIN   │  ← platform-level (global_role)
                    │  (global)     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌───▼──────┐
        │  OWNER   │ │  MEMBER  │ │  VIEWER  │  ← workspace-level (role)
        │ (ws)     │ │  (ws)    │ │  (ws)    │
        └──────────┘ └──────────┘ └──────────┘
```

### 1.2 Role Definitions

| Role | Scope | Description |
|------|-------|-------------|
| `superadmin` | Platform | Full system access. Manage all users, all workspaces. Only one exists. |
| `owner` | Workspace | Full workspace control. Manage members, settings, billing, all content. |
| `member` | Workspace | Content creation and management. Cannot manage people or billing. |
| `viewer` | Workspace | Read-only access to channels, projects, jobs, analytics. |

### 1.3 Role Storage

**Database Tables:**
- `users.role` — global role: `superadmin` | `user`
- `workspace_members.role` — workspace role: `owner` | `member` | `viewer`

**JWT Claims:**
```json
{
  "sub": "1",
  "email": "user@example.com",
  "role": "owner",        // workspace role
  "global_role": "user",  // platform role
  "wid": 1                // active workspace ID
}
```

### 1.4 Role Resolution (Principal)

File: `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/services/dashboard/v2/_deps.py:25-33`

```python
@dataclass
class Principal:
    user_id: int | None
    email: str | None
    role: str          # workspace-scoped: owner | member | viewer
    source: str        # 'legacy' | 'v2_jwt'
    workspace_id: int  # active workspace
    global_role: str   # platform-level: superadmin | user
```

**Resolution order:**
1. Authorization Bearer header (JWT or legacy token)
2. HttpOnly `access_token` cookie
3. Legacy in-memory session map

**Membership check:** On every request, verifies user is still a member of the workspace. Returns 403 `workspace_access_revoked` if removed.

---

## Part 2: Permission Matrix

### 2.1 All Permissions (33 total)

File: `@/Users/saurabhrawat/Desktop/projects/Autoniix/tests/test_workspace_permissions.py:39-79`

#### Workspace Domain (13)
| Permission | Description |
|-----------|-------------|
| `workspace.view` | View workspace details |
| `workspace.settings.view` | View workspace settings |
| `workspace.settings.edit` | Edit workspace settings |
| `workspace.billing.view` | View billing info |
| `workspace.billing.manage` | Manage billing |
| `workspace.members.view` | View workspace members |
| `workspace.members.invite` | Invite new members |
| `workspace.members.remove` | Remove members |
| `workspace.members.role.change` | Change member roles |
| `workspace.ownership.transfer` | Transfer ownership |
| `workspace.integrations.view` | View integrations |
| `workspace.integrations.manage` | Manage integrations |
| `workspace.audit_log.view` | View audit log |

#### Channel Domain (6)
| Permission | Description |
|-----------|-------------|
| `channel.view` | View channels |
| `channel.create` | Create channels |
| `channel.settings.edit` | Edit channel settings |
| `channel.delete` | Delete channels |
| `channel.credentials.view.labels` | View credential labels |
| `channel.credentials.manage` | Manage channel credentials |

#### Project Domain (6)
| Permission | Description |
|-----------|-------------|
| `project.view` | View projects |
| `project.create` | Create projects |
| `project.edit` | Edit projects |
| `project.delete` | Delete projects |
| `project.approve` | Approve projects |
| `project.publish` | Publish projects |

#### Jobs Domain (4)
| Permission | Description |
|-----------|-------------|
| `job.view` | View jobs |
| `job.trigger` | Trigger jobs |
| `job.cancel` | Cancel jobs |
| `job.retry` | Retry jobs |

#### Analytics Domain (2)
| Permission | Description |
|-----------|-------------|
| `analytics.view` | View analytics |
| `analytics.export` | Export analytics |

#### Credentials Domain (2)
| Permission | Description |
|-----------|-------------|
| `credentials.view.labels` | View credential labels |
| `credentials.view.manage` | Manage credentials |

### 2.2 Role → Permission Mapping

| Role | Count | Permissions |
|------|-------|-------------|
| **owner** | 33 | ALL permissions |
| **member** | 24 | All except: `workspace.settings.edit`, `workspace.billing.*`, `workspace.members.invite/remove/role.change`, `workspace.ownership.transfer`, `workspace.integrations.manage`, `workspace.audit_log.view` |
| **viewer** | 5 | `workspace.view`, `channel.view`, `project.view`, `job.view`, `analytics.view` |

### 2.3 Permission Enforcement

**Three enforcement mechanisms:**

1. **`require_role(*roles)`** — Simple role allowlist (owner bypass always)
   ```python
   @router.post("/channels")
   async def create(actor: Principal = Depends(require_role("owner", "member"))):
   ```

2. **`require_global_role(*roles)`** — Platform-level role check
   ```python
   @router.get("/users")
   async def list_users(_: Principal = Depends(require_global_role("superadmin"))):
   ```

3. **`require_permission(permission)`** — Named permission from RBAC matrix
   ```python
   @router.put("/members/{id}/role")
   async def set_role(actor: Principal = Depends(require_permission("workspace.members.role.change"))):
   ```

### 2.4 Permission Cache

File: `@/Users/saurabhrawat/Desktop/projects/Autoniix/src/services/dashboard/v2/_permissions.py`

- **TTL:** 30 seconds in-process cache
- **Invalidation:** Redis pub/sub channel `permissions.invalidate`
- **Startup probe:** Verifies owner role has permissions on app start
- **Fail-closed:** Unknown permissions always deny (403)

---

## Part 3: Section Visibility Rules

### 3.1 Sidebar Visibility Matrix

Each sidebar item has visibility rules based on permissions and global role.

File: `@/Users/saurabhrawat/Desktop/projects/Autoniix/dashboard/src/lib/components/Sidebar.tsx:62-103`

| Section | Route | Visibility Rule |
|---------|-------|-----------------|
| Home | `/dashboard` | Always visible |
| Notifications | `/dashboard/notifications` | Always visible |
| Channels | `/dashboard/channels` | Always visible |
| Content | `/dashboard/content` | Always visible |
| Library | `/dashboard/library` | `project.view` permission |
| Schedule | `/dashboard/content/calendar` | Always visible |
| Queue | `/dashboard/queue` | Always visible |
| Progress | `/dashboard/progress` | Always visible |
| Review | `/dashboard/review` | Always visible |
| Fleet | `/dashboard/fleet` | `workspace.settings.edit` permission |
| Analytics | `/dashboard/analytics` | Always visible |
| Experiments | `/dashboard/experiments` | `workspace.settings.edit` permission |
| Workspace | `/dashboard/workspace` | `workspace.view` permission |
| Teams | `/dashboard/teams` | `workspace.members.view` permission |
| Users | `/dashboard/users` | `superadmin` global role |
| Providers | `/dashboard/providers` | `credentials.view.labels` permission |
| Settings | `/dashboard/settings` | `workspace.settings.edit` permission |
| Debug | `/dashboard/debug` | `workspace.settings.edit` permission |

### 3.2 Feature-Level Visibility (within a section)

**To be implemented:** Fine-grained visibility within sections. Examples:

| Section | Feature | Visibility Rule |
|---------|---------|-----------------|
| Channels | Delete button | `channel.delete` permission |
| Channels | Trigger button | `job.trigger` permission |
| Channels | Provider overrides | `channel.credentials.manage` permission |
| Workspace | Invite button | `workspace.members.invite` permission |
| Workspace | Transfer ownership | `workspace.ownership.transfer` permission |
| Workspace | Billing tab | `workspace.billing.view` permission |
| Workspace | Audit log tab | `workspace.audit_log.view` permission |
| Providers | Add credential | `credentials.view.manage` permission |
| Providers | Change requests | `credentials.view.manage` permission |
| Settings | Feature flags | `workspace.settings.edit` permission |
| Settings | Clean slate | `workspace.settings.edit` permission |
| Content | Bulk actions | `project.approve` permission |
| Content | Delete content | `project.delete` permission |
| Review | Approve/Reject | `project.approve` permission |
| Jobs | Retry/Restart | `job.retry` permission |
| Jobs | Cancel | `job.cancel` permission |
| Analytics | Export | `analytics.export` permission |

---

## Part 4: Feature Flags System

### 4.1 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   FEATURE FLAGS SYSTEM                        │
│                                                              │
│  feature_flags table (Postgres)                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ key (TEXT PK)  │ enabled (BOOL) │ payload (JSONB)    │    │
│  │ description    │ updated_at     │                    │    │
│  └──────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────┐    ┌──────────────────────┐            │
│  │ Dashboard API    │    │ Pipeline Services     │            │
│  │ (v2/flags.py)    │    │ (src/flags.py)        │            │
│  │                  │    │                       │            │
│  │ GET /flags       │    │ get_flag(key)         │            │
│  │ PUT /flags/{key} │    │ get_flag_sync(key)    │            │
│  │                  │    │ invalidate_cache(key) │            │
│  └─────────────────┘    └──────────────────────┘            │
│         │                         │                          │
│         ▼                         ▼                          │
│  30s TTL cache             30s TTL cache                     │
│  (in-process)              (in-process)                      │
│                                                              │
│  Dashboard cache: _deps.flag_enabled()                       │
│  Pipeline cache:  src/flags.py get_flag()                    │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Flag Categories

#### Auth Domain
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `auth.v2.enabled` | bool | true | Enable v2 JWT auth |
| `auth.mfa.required` | bool | false | Require MFA for all users |
| `auth.password.min_length` | int | 8 | Minimum password length |

#### Provider Domain
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `providers.admin_credentials.enabled` | bool | false | Allow members to manage credentials |
| `providers.auto_health_check.enabled` | bool | true | Auto health-check credentials |
| `providers.rotation_reminder_days` | int | 90 | Days before rotation warning |

#### Pipeline Domain
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `pipeline.human_review.default` | string | "first_10" | Default review policy |
| `pipeline.max_concurrent_jobs` | int | 5 | Max concurrent video jobs |
| `pipeline.auto_retry.enabled` | bool | true | Auto-retry failed jobs |
| `pipeline.auto_retry.max_attempts` | int | 3 | Max auto-retry attempts |
| `pipeline.cost_tracking.enabled` | bool | true | Track per-phase costs |

#### LLM Domain
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `llm.compression.tier` | string | "off" | Prompt compression tier (off/fast/max) |
| `llm.router.fallback.enabled` | bool | true | Enable LLM router fallback |
| `llm.cost.budget.daily` | float | 50.0 | Daily LLM cost budget |

#### Brain Domain (Agentic)
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `brain.critic.enabled` | bool | false | Enable critic agent |
| `brain.reflector.enabled` | bool | false | Enable reflector agent |
| `brain.preventor.enabled` | bool | false | Enable preventor agent |
| `brain.llm_reasoning.enabled` | bool | false | Enable LLM reasoning |
| `brain.decision_threshold` | float | 0.7 | Confidence threshold for auto-decisions |

#### Experiment Domain
| Flag Key | Type | Default | Description |
|----------|------|---------|-------------|
| `experiments.bandit.enabled` | bool | true | Enable bandit-based assignment |
| `experiments.auto_apply_winner` | bool | false | Auto-apply winning variant |

### 4.3 Flag Usage Patterns

**In Dashboard API (FastAPI dependency):**
```python
from ._deps import flag_enabled

if await flag_enabled("providers.admin_credentials.enabled"):
    # Allow member access
```

**In Pipeline Services (async):**
```python
from src.flags import get_flag

tier = await get_flag("llm.compression.tier", default="off")
```

**In Pipeline Services (sync):**
```python
from src.flags import get_flag_sync

max_jobs = get_flag_sync("pipeline.max_concurrent_jobs", default=5)
```

---

## Part 5: System Configuration

### 5.1 System Config Table

```
system_config table:
┌──────────────────────────────────────────────────────────┐
│ config_key (TEXT PK) │ config_value (TEXT) │ description │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Known Config Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `daily_budget_limit` | float | 50.0 | Global daily API spend cap |
| `emergency_stop` | bool | false | Freeze all operations |
| `environment_mode` | string | "production" | production / test |
| `temporal_production_max_activities` | int | 10 | Max concurrent Temporal activities |
| `temporal_scheduler_max_activities` | int | 5 | Max scheduler activities |
| `db_statement_timeout_ms` | int | 30000 | DB statement timeout |

### 5.3 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/system/config` | GET | List all config |
| `/api/v2/system/config` | PUT | Update config value |
| `/api/v2/system/emergency-stop` | POST | Set emergency_stop=true |
| `/api/v2/system/emergency-resume` | POST | Set emergency_stop=false |
| `/api/v2/system/environment` | GET | Environment info |
| `/api/v2/system/clean-slate` | POST | Full system reset |

---

## Part 6: Scope Resolution Engine (to be formalized)

### 6.1 Scope Hierarchy

```
Platform (superadmin)
  └── Workspace (workspace_id)
        ├── Workspace-level config (default)
        ├── Channel (channel_id)
        │     ├── Channel-level config (overrides workspace)
        │     └── Content Mode (short / long_form)
        │           └── Mode-level config (overrides channel)
        └── Brand (brand_id)
              └── Brand-level config
```

### 6.2 Resolution Order (for provider chains, settings, quotas)

```
1. channel_id + content_mode  (most specific)
2. channel_id + NULL          (channel-level default)
3. NULL + content_mode        (workspace mode-level)
4. NULL + NULL                (workspace default)
```

### 6.3 Scope-Aware Entities

| Entity | Scope Levels |
|--------|-------------|
| Provider Credentials | workspace, channel, content_mode |
| Provider Chains | workspace, channel, content_mode |
| Routing Policies | workspace, channel |
| Quotas | workspace, channel, category |
| Brand Kits | workspace, brand |
| Asset Collections | workspace, channel |
| Settings | workspace, channel |

---

## Part 7: Quota & Limit Engine (to be formalized)

### 7.1 Quota Types

| Quota | Scope | Enforcement Point |
|-------|-------|-------------------|
| Daily API spend (global) | Platform | Trigger endpoint |
| Daily API spend (channel) | Channel | Trigger endpoint |
| Monthly provider spend | Workspace | Provider router |
| Storage quota | Workspace | Asset upload |
| Concurrent jobs | Platform | Trigger endpoint |
| Videos per week (short) | Channel | Scheduler |
| Videos per week (long) | Channel | Scheduler |
| Review timeout | Channel | Review workflow |

### 7.2 Quota Enforcement

```
Request → Check global daily budget → Check channel daily budget
       → Check monthly provider quota → Check concurrent job limit
       → Check weekly video limit → Proceed or 400/409
```

---

## Part 8: Audit Trail

### 8.1 Audit Log Table

```
audit_log_v2:
┌────────────────────────────────────────────────────────────┐
│ actor_user_id  │ actor_label  │ action         │ source   │
│ target_type    │ target_id    │ before (JSONB) │ after    │
│ request_id     │ ip           │ user_agent     │ ts       │
└────────────────────────────────────────────────────────────┘
```

### 8.2 Audited Actions

Every mutation endpoint calls `audit()` from `_deps.py`. Actions include:
- `channel.create/update/delete/enable/disable/archive/restore/clone`
- `member.role_change/remove`
- `invite.create/revoke`
- `workspace.update`
- `flag.update`
- `credential.create/update/delete/rotate`
- `notification.route.create/update/delete`
- `job.approve/reject/retry/stop`

---

## Part 9: Models to Build

### 9.1 RuleEngine Model

```python
class RuleEngine:
    """Central rule evaluation engine."""
    
    def evaluate(self, principal: Principal, resource: str, action: str) -> bool:
        """Check if principal can perform action on resource."""
        
    def visible_sections(self, principal: Principal) -> list[str]:
        """Return sections visible to principal."""
        
    def visible_features(self, principal: Principal, section: str) -> list[str]:
        """Return features visible within a section."""
        
    def resolve_scope(self, workspace_id: int, channel_id: str | None, 
                      content_mode: str | None) -> ScopeConfig:
        """Resolve effective config for a scope."""
```

### 9.2 GlobalConfig Model

```python
class GlobalConfig:
    """Centralized configuration store."""
    
    # System configs
    daily_budget_limit: float
    emergency_stop: bool
    environment_mode: str
    
    # Feature flags (dynamic)
    flags: dict[str, Any]
    
    # Permission matrix
    role_permissions: dict[str, set[str]]
    
    # Section visibility
    section_visibility: dict[str, list[str]]  # section → required permissions
    
    # Feature visibility
    feature_visibility: dict[str, dict[str, list[str]]]  # section → feature → permissions
    
    # Quota limits
    quotas: dict[str, QuotaConfig]
    
    # Scope resolution rules
    scope_resolution_order: list[str]  # ["channel+mode", "channel", "workspace+mode", "workspace"]
```

### 9.3 ScopeConfig Model

```python
class ScopeConfig:
    """Resolved configuration for a specific scope."""
    
    workspace_id: int
    channel_id: str | None
    content_mode: str | None
    
    # Resolved values (most specific wins)
    provider_chain: list[int]  # credential IDs in priority order
    routing_policy: str
    quota: QuotaConfig | None
    settings: dict[str, Any]
```

### 9.4 SectionAccess Model

```python
class SectionAccess:
    """Defines who can see/access what."""
    
    section_id: str          # e.g., "S03-CHANNELS"
    route: str               # e.g., "/dashboard/channels"
    label: str               # e.g., "Channels"
    icon: str                # e.g., "Tv"
    pillar: str              # e.g., "create"
    
    # Access rules
    required_permissions: list[str]     # Any one suffices
    required_global_role: str | None    # e.g., "superadmin"
    required_feature_flag: str | None   # e.g., "channels.v2.enabled"
    
    # Child features
    features: list[FeatureAccess]
    
class FeatureAccess:
    """Defines who can access a specific feature within a section."""
    
    feature_id: str          # e.g., "channel.delete"
    label: str               # e.g., "Delete Channel"
    required_permissions: list[str]
    required_role: str | None
    required_feature_flag: str | None
```

---

## Part 10: Implementation Plan

### Phase 1: Models & Database
1. Create `SectionAccess` and `FeatureAccess` tables in DB
2. Create `ScopeConfig` resolution logic
3. Seed section visibility rules from this document

### Phase 2: Rule Engine
1. Build `RuleEngine` class with all evaluation methods
2. Integrate with existing `require_permission` dependency
3. Add `require_feature(feature_id)` dependency
4. Add `require_section(section_id)` dependency

### Phase 3: Global Config API
1. Build `GET /api/v2/admin/config` — full config dump
2. Build `PUT /api/v2/admin/config` — bulk config update
3. Build `GET /api/v2/admin/sections` — section visibility matrix
4. Build `PUT /api/v2/admin/sections/{id}` — update section rules

### Phase 4: Frontend Integration
1. `usePermissions()` hook already exists — extend with feature-level checks
2. `useSectionAccess()` — new hook for section visibility
3. `useFeatureAccess(featureId)` — new hook for feature-level gating
4. Config admin page for managing rules (superadmin only)

---

## Appendix: Current Implementation Status

| Component | Status | File |
|-----------|--------|------|
| Principal model | ✅ Done | `_deps.py:25-33` |
| require_role | ✅ Done | `_deps.py:106-115` |
| require_global_role | ✅ Done | `_deps.py:118-137` |
| require_permission | ✅ Done | `_deps.py:140-157` |
| Permission cache | ✅ Done | `_permissions.py` |
| Permission matrix (DB) | ✅ Done | `202605220001_named_permissions.sql` |
| Feature flags (DB) | ✅ Done | `feature_flags` table |
| Feature flags (API) | ✅ Done | `flags.py` |
| Feature flags (pipeline) | ✅ Done | `src/flags.py` |
| System config | ✅ Done | `system_config` table + API |
| Audit log | ✅ Done | `audit_log_v2` table + `audit()` |
| Section visibility (FE) | ✅ Partial | `Sidebar.tsx` — hardcoded rules |
| Feature visibility (FE) | ❌ Missing | No feature-level gating |
| RuleEngine class | ❌ Missing | To be built |
| GlobalConfig model | ❌ Missing | To be built |
| ScopeConfig resolver | ❌ Partial | Provider chains only |
| SectionAccess model | ❌ Missing | To be built |
| Config admin UI | ❌ Missing | To be built |
