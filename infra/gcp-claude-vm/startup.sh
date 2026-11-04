#!/usr/bin/env bash
# Startup script for the "claude" VM: installs Node.js 22 + Claude Code system-wide.
# Idempotent: safe to run on every boot.
set -euo pipefail
exec > >(tee -a /var/log/claude-startup.log) 2>&1
echo "[$(date -Is)] claude-vm startup begin"

MARKER=/var/lib/claude-vm/installed
if [[ ! -f "$MARKER" ]]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git tmux ripgrep jq unattended-upgrades

  # Node.js 22 LTS from NodeSource (signed repo)
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update -y
  apt-get install -y nodejs

  # Automatic security patches
  dpkg-reconfigure -f noninteractive unattended-upgrades

  install -d /var/lib/claude-vm
  touch "$MARKER"
fi

# Install / update Claude Code on every boot
npm install -g @anthropic-ai/claude-code@latest

# Optional: expose ANTHROPIC_API_KEY from Secret Manager at login (only if the
# secret exists and the VM service account can read it). Otherwise users run
# `claude` and sign in with their Claude account via the printed URL.
cat > /etc/profile.d/claude-key.sh <<'PROFILE'
if [ -z "${ANTHROPIC_API_KEY:-}" ] && command -v gcloud >/dev/null 2>&1; then
  _k=$(gcloud secrets versions access latest --secret=anthropic-api-key 2>/dev/null) && export ANTHROPIC_API_KEY="$_k"
  unset _k
fi
PROFILE
chmod 0644 /etc/profile.d/claude-key.sh

echo "[$(date -Is)] claude-vm startup done: $(claude --version 2>/dev/null || echo 'claude not found')"
