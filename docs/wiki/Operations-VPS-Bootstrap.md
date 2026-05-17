# Operations: VPS Bootstrap

## Purpose

Fresh server provisioning. `scripts/vps_bootstrap.sh` is an idempotent
script run once on a new Hetzner / DO / Hostinger VPS.

## What it does

- UFW firewall: deny incoming, allow 22 (SSH), 80, 443 only.
- fail2ban with default jail.local for sshd.
- Docker + Compose plugin (latest stable, official apt repos).
- Swap file (2× RAM, capped at 16G) so renders survive memory spikes.
- `/mnt/backups` mount + cron entry calling `scripts/backup.sh`.
- Creates the `autoniix` system user with Docker group membership.
- Configures unattended-upgrades for security patches only.

## Usage

```bash
# As root on a fresh server:
curl -fsSL https://raw.githubusercontent.com/saurabhrawat-gh/Autoniix/main/scripts/vps_bootstrap.sh \
  | bash -s -- --hostname autoniix-prod --email ops@example.com
```

Idempotent: re-running only fills in missing pieces.

## Split-host Traefik

The production setup uses six subdomains, all pointing the same `A`
record to the VPS:

```
dash.example.com        → dashboard-ui
api.example.com         → dashboard-bff
grafana.example.com     → grafana
prometheus.example.com  → prometheus (admin-auth)
alerts.example.com      → alertmanager (admin-auth)
temporal.example.com    → temporal-ui (admin-auth)
```

## Hardening

From `docs/OPERATIONS-RUNBOOK.md`:

- SSH key only (PasswordAuthentication=no).
- `AllowUsers autoniix` only.
- `PermitRootLogin no`.
- Custom SSH port (optional).
- `sysctl` tweaks: TCP timestamps off, SYN cookies on, IPv6 RA off.

## Related pages

- [[Operations-Runbook]] · [[Security-Network-TLS-Hardening]] ·
  [[Architecture-Network-And-Gateway]]
