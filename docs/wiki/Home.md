# Autoniix Wiki

> Self-hosted, AI-driven YouTube content factory. Temporal-orchestrated,
> Python (FastAPI) microservices, Remotion render engine, Next.js dashboard.

**Repo:** `saurabhrawat-gh/Autoniix` &nbsp; **Status:** production-ready (Phase G done)

## Quick links

- [[Architecture-Overview]] — system diagram, decisions, data flow
- [[Workflow-VideoProduction]] — the 13-phase pipeline
- [[Operations-Runbook]] — deploy, backup, smoke tests
- [[Test-vs-Production-Mode]] — how the test/prod switch works
- [[Appendix-Endpoints-Index]] — every BFF endpoint
- [[Appendix-Env-Vars]] — every env var

## Table of Contents

### Architecture
- [[Architecture-Overview]]
- [[Architecture-Data-Layer]]
- [[Architecture-Network-And-Gateway]]
- [[Architecture-Container-Topology]]
- [[Architecture-Provider-Pattern]]

### Temporal Workflows
- [[Workflow-VideoProduction]]
- [[Workflow-DailyScheduler]]
- [[Workflow-GateCalibration]]
- [[Workflow-NichePulseRefresh]]
- [[Workflow-RetentionFetch]]
- [[Workflow-ModelMaintenance]]
- [[Workers-And-Activities]]
- [[Schedules]]

### Application Services
- [[Service-Research]]
- [[Service-Script]]
- [[Service-Voice]]
- [[Service-Assets]]
- [[Service-Thumbnail]]
- [[Service-Assembly]]
- [[Service-Delivery]]
- [[Service-Analytics]]
- [[Service-Admin]]
- [[Service-Direction]]
- [[Service-Brand]]
- [[Service-Editor]]
- [[Service-SheetsSync]]
- [[Service-Remotion]]

### Providers
- [[Providers-LLM]]
- [[Providers-TTS]]
- [[Providers-Image]]
- [[Providers-Search]]
- [[Providers-Storage]]
- [[Providers-Secrets]]

### Dashboard BFF
- [[BFF-Auth-v2]]
- [[BFF-Workspaces-And-Multitenancy]]
- [[BFF-Channels]]
- [[BFF-Jobs-And-Content]]
- [[BFF-System-And-FleetHealth]]
- [[BFF-Library-DAM]]
- [[BFF-Providers-And-Experiments]]
- [[BFF-Notifications-Review-Users-Flags]]
- [[BFF-Legacy-API-Deprecation]]

### Dashboard UI
- [[UI-Auth-Pages]]
- [[UI-Dashboard-Home-And-Channels]]
- [[UI-Content-And-Library]]
- [[UI-Progress-And-Jobs]]
- [[UI-Queue-And-Review]]
- [[UI-Experiments-And-Providers]]
- [[UI-Settings-And-Workspace]]
- [[UI-Notifications-Users-Profile]]
- [[UI-Fleet-Debug-UIKit]]
- [[UI-Theming-And-Components]]

### Database
- [[DB-Schema]]
- [[DB-Migrations]]
- [[DB-Seed-Data]]

### Intelligence / ML
- [[ML-GBM-Models]]
- [[ML-Bandits-And-Experiments]]
- [[ML-Self-Learning-Loop]]

### Quality & Environments
- [[Quality-Gates]]
- [[Test-vs-Production-Mode]]
- [[Cost-Analysis]]

### Observability & Ops
- [[Observability-Prometheus-Grafana]]
- [[Observability-Logs-Loki]]
- [[Observability-Alerts]]
- [[Operations-Runbook]]
- [[Operations-VPS-Bootstrap]]

### Security
- [[Security-Authn-Authz]]
- [[Security-Network-TLS-Hardening]]

### Testing & CI
- [[Testing-Strategy]]
- [[CI-CD]]

### Reference
- [[Appendix-Env-Vars]]
- [[Appendix-Endpoints-Index]]
- [[Appendix-Glossary]]
