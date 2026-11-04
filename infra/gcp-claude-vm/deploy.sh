#!/usr/bin/env bash
# Deploy a hardened Compute Engine VM named "claude" to run Claude Code.
#
#   PROJECT_ID=my-project ./deploy.sh            # create/update everything
#   PROJECT_ID=my-project ./deploy.sh --destroy  # remove the VM (keeps network/SA)
#
# Design: no public IP, SSH only via Identity-Aware Proxy, outbound internet via
# Cloud NAT, OS Login, Shielded VM, dedicated least-privilege service account.
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID}"
VM_NAME="${VM_NAME:-claude}"                # GCE names must be lowercase
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-${REGION}-a}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-medium}"   # 2 vCPU / 4 GB
DISK_SIZE="${DISK_SIZE:-20GB}"
IMAGE_FAMILY="${IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${IMAGE_PROJECT:-debian-cloud}"
NETWORK="${NETWORK:-default}"
SA_NAME="${SA_NAME:-claude-vm}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
ROUTER="claude-router-${REGION}"
NAT="claude-nat-${REGION}"
TAG="claude-vm"
HERE="$(cd "$(dirname "$0")" && pwd)"

g() { gcloud --project="$PROJECT_ID" --quiet "$@"; }
exists() { "$@" >/dev/null 2>&1; }

if [[ "${1:-}" == "--destroy" ]]; then
  g compute instances delete "$VM_NAME" --zone="$ZONE"
  exit 0
fi

echo ">> Enabling APIs"
g services enable compute.googleapis.com iap.googleapis.com secretmanager.googleapis.com

echo ">> Service account ${SA_EMAIL}"
exists g iam service-accounts describe "$SA_EMAIL" || \
  g iam service-accounts create "$SA_NAME" --display-name="Claude VM"
for role in roles/logging.logWriter roles/monitoring.metricWriter; do
  g projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" --role="$role" --condition=None >/dev/null
done
# Let the VM read ONLY the anthropic-api-key secret, if you created it.
if exists g secrets describe anthropic-api-key; then
  g secrets add-iam-policy-binding anthropic-api-key \
    --member="serviceAccount:${SA_EMAIL}" --role=roles/secretmanager.secretAccessor >/dev/null
fi

echo ">> Firewall: SSH from IAP range only"
exists g compute firewall-rules describe allow-iap-ssh-claude || \
  g compute firewall-rules create allow-iap-ssh-claude --network="$NETWORK" \
    --direction=INGRESS --action=allow --rules=tcp:22 \
    --source-ranges=35.235.240.0/20 --target-tags="$TAG"

echo ">> Cloud Router + NAT for outbound internet (npm, api.anthropic.com)"
exists g compute routers describe "$ROUTER" --region="$REGION" || \
  g compute routers create "$ROUTER" --network="$NETWORK" --region="$REGION"
exists g compute routers nats describe "$NAT" --router="$ROUTER" --region="$REGION" || \
  g compute routers nats create "$NAT" --router="$ROUTER" --region="$REGION" \
    --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges

echo ">> VM ${VM_NAME} in ${ZONE}"
if exists g compute instances describe "$VM_NAME" --zone="$ZONE"; then
  g compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
    --metadata-from-file=startup-script="$HERE/startup.sh"
  echo "   VM exists; startup script updated (runs on next boot)."
else
  g compute instances create "$VM_NAME" --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT" \
    --boot-disk-size="$DISK_SIZE" --boot-disk-type=pd-balanced \
    --network="$NETWORK" --no-address --tags="$TAG" \
    --service-account="$SA_EMAIL" --scopes=cloud-platform \
    --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring \
    --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE \
    --metadata-from-file=startup-script="$HERE/startup.sh" \
    --labels=app=claude-code,owner=etchworks
fi

cat <<MSG

Done. Install takes ~2-3 min after boot. Watch it with:
  gcloud compute ssh $VM_NAME --project=$PROJECT_ID --zone=$ZONE --tunnel-through-iap \\
    --command='sudo tail -f /var/log/claude-startup.log'

Then connect and run Claude Code (use tmux so sessions survive disconnects):
  gcloud compute ssh $VM_NAME --project=$PROJECT_ID --zone=$ZONE --tunnel-through-iap
  tmux new -As claude
  claude
MSG
