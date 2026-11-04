# `claude` VM on Google Cloud

Creates a Compute Engine VM named **`claude`** that runs [Claude Code](https://docs.claude.com/en/docs/claude-code).
(GCE instance names must be lowercase, so `Claude` becomes `claude`.)

## Deploy (Cloud Shell or any machine with `gcloud`)

```bash
gcloud auth login
PROJECT_ID=<your-project-id> ./deploy.sh
```

Optional overrides: `ZONE`, `REGION`, `MACHINE_TYPE` (default `e2-medium`), `DISK_SIZE`, `NETWORK`.

## What it builds

| Piece | Setting | Why |
|---|---|---|
| VM | `e2-medium`, Debian 12, 20 GB pd-balanced | ~US$25/mo running; stop it when idle |
| Ingress | No public IP; SSH only from IAP (`35.235.240.0/20`) | Nothing exposed to the internet |
| Egress | Cloud Router + Cloud NAT | npm + `api.anthropic.com` reachable |
| Identity | OS Login, project SSH keys blocked | Access controlled by IAM |
| Hardening | Shielded VM (secure boot, vTPM, integrity) + unattended-upgrades | |
| Service account | `claude-vm`, log/metric writer only | Least privilege |
| Software | Node.js 22, Claude Code (updated each boot), git, tmux, ripgrep | |

## Signing in to Claude

- **Claude subscription:** run `claude` and open the printed login URL.
- **API key:** store it in Secret Manager, then re-run `deploy.sh` so the VM can read it:
  ```bash
  printf '%s' "$KEY" | gcloud secrets create anthropic-api-key --data-file=- --project=$PROJECT_ID
  ```
  It is loaded into `ANTHROPIC_API_KEY` at login. It is never stored in instance metadata.

## Day-to-day

```bash
gcloud compute ssh claude --zone us-central1-a --tunnel-through-iap   # connect
tmux new -As claude && claude                                          # run
gcloud compute instances stop claude --zone us-central1-a              # save cost
PROJECT_ID=<id> ./deploy.sh --destroy                                  # delete VM
```

Your account needs `roles/iap.tunnelResourceAccessor` and `roles/compute.osAdminLogin` (or Owner) to connect.
