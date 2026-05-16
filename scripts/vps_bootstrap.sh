#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Autoniix — one-shot VPS bootstrap (Ubuntu 22.04 / 24.04)
# ─────────────────────────────────────────────────────────────────────
# Run ONCE as root on a fresh Hostinger / Hetzner / DO VPS:
#
#   curl -fsSL https://raw.githubusercontent.com/<you>/yt-automation-n8n/main/scripts/vps_bootstrap.sh | sudo bash
#
# Or after `git clone` as root:
#
#   sudo bash scripts/vps_bootstrap.sh
#
# What it does (idempotent — safe to re-run):
#   • Creates non-root `autoniix` deploy user with sudo + your SSH key
#   • Hardens SSH: disables root login + password auth, moves to port 2222
#   • Enables UFW with 2222/tcp + 80/tcp + 443/tcp only
#   • Installs + configures fail2ban (sshd jail)
#   • Installs Docker Engine + Compose plugin
#   • Creates 4 GB swap file (helps burst memory on Remotion renders)
#   • Configures Docker daemon: log rotation, default ulimits
#   • Creates /mnt/backups owned by autoniix (backup target)
#
# Required env vars (export before running, or set inline):
#   DEPLOY_SSH_PUBKEY   — your laptop's public SSH key (mandatory)
#   SSH_PORT            — default 2222 (override if your firewall blocks)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Must run as root (use sudo)"; exit 1; }

: "${DEPLOY_SSH_PUBKEY:?Set DEPLOY_SSH_PUBKEY to your public key (ssh-ed25519 ... user@host)}"
SSH_PORT="${SSH_PORT:-2222}"
DEPLOY_USER="autoniix"

log() { printf '\n\033[1;32m[bootstrap]\033[0m %s\n' "$*"; }

log "1/9  System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl gnupg lsb-release \
    ufw fail2ban git make unzip jq htop tmux \
    rsync cron logrotate

log "2/9  Deploy user: ${DEPLOY_USER}"
if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "${DEPLOY_USER}"
    usermod -aG sudo "${DEPLOY_USER}"
fi
# Passwordless sudo for the deploy user (CI/CD requires it for `docker compose ...`)
echo "${DEPLOY_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${DEPLOY_USER}"
chmod 440 "/etc/sudoers.d/90-${DEPLOY_USER}"

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
AUTHKEYS="/home/${DEPLOY_USER}/.ssh/authorized_keys"
touch "${AUTHKEYS}"
chmod 600 "${AUTHKEYS}"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "${AUTHKEYS}"
grep -qxF "${DEPLOY_SSH_PUBKEY}" "${AUTHKEYS}" || echo "${DEPLOY_SSH_PUBKEY}" >> "${AUTHKEYS}"

log "3/9  SSH hardening (port ${SSH_PORT}, no root, no password)"
SSHD_CFG=/etc/ssh/sshd_config.d/99-autoniix.conf
cat > "${SSHD_CFG}" <<EOF
Port ${SSH_PORT}
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
AllowUsers ${DEPLOY_USER}
EOF
# Validate config before restart so we don't lock ourselves out
sshd -t -f /etc/ssh/sshd_config

log "4/9  Firewall (UFW)"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment 'ssh'
ufw allow 80/tcp comment 'http (le challenge + redirect)'
ufw allow 443/tcp comment 'https'
ufw --force enable

log "5/9  fail2ban (sshd jail)"
cat > /etc/fail2ban/jail.d/autoniix-sshd.local <<EOF
[sshd]
enabled = true
port = ${SSH_PORT}
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

log "6/9  Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    UBUNTU_CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "${DEPLOY_USER}"

# Docker daemon: log rotation + sane defaults
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" },
  "default-ulimits": { "nofile": { "Name": "nofile", "Hard": 65535, "Soft": 65535 } },
  "live-restore": true
}
EOF
systemctl enable --now docker
systemctl restart docker

log "7/9  Swap (4 GB)"
if ! swapon --show | grep -q '/swapfile'; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -qxF '/swapfile none swap sw 0 0' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=10
    grep -qxF 'vm.swappiness=10' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

log "8/9  Backup directory /mnt/backups"
install -d -m 750 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /mnt/backups

log "9/9  Restart sshd"
systemctl restart ssh || systemctl restart sshd

cat <<EOF

────────────────────────────────────────────────────────────────────
  Bootstrap complete.

  Next steps from your laptop:
    ssh -p ${SSH_PORT} ${DEPLOY_USER}@<vps-ip>
    git clone git@github.com:<you>/yt-automation-n8n.git ~/autoniix
    cd ~/autoniix
    cp .env.production.example .env
    \$EDITOR .env              # fill in all secrets
    make deploy-check
    docker compose --profile tls up -d --build
    make schedule-register
    make auth-enable
    make smoke

  SSH port:     ${SSH_PORT}
  Deploy user:  ${DEPLOY_USER}
  Backup dir:   /mnt/backups
────────────────────────────────────────────────────────────────────
EOF
