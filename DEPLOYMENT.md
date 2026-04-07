# Deployment

This repository is set up for a simple production flow:

1. push to `master`
2. GitHub Actions runs tests and flake8
3. GitHub builds a Docker image and pushes it to `ghcr.io/suchokrates1/lista-obecnosci`
4. GitHub connects to `rpi` through Tailscale and updates the running container

## GitHub secrets

Configure these repository secrets in GitHub:

- `TS_OAUTH_CLIENT_ID`: the same Tailscale OAuth client id already used by other homelab deploy workflows
- `TS_OAUTH_SECRET`: the matching Tailscale OAuth secret
- `SSH_PRIVATE_KEY`: private key that can SSH to `suchokrates1@100.66.220.72`

`GITHUB_TOKEN` is already used automatically for pushing the image from Actions to GHCR.
The deploy step assumes the GHCR package is public, so the server can pull it without a separate registry secret.

## Server preparation

Run these steps once on `rpi`:

```bash
hostname
cd /home/suchokrates1
git clone https://github.com/suchokrates1/lista-obecnosci.git obecnosc
cd /home/suchokrates1/obecnosc
cp .env.example .env
mkdir -p reports invoices static
docker volume create obecnosc-instance
```

Fill `.env` with the real values. Do not commit it.

The Word templates are not stored in Git, so keep these files on the server:

- `szablon.docx`
- `rejestr.docx`

Then perform the first manual deployment:

```bash
export APP_IMAGE=ghcr.io/suchokrates1/lista-obecnosci:latest
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml run --rm web flask db upgrade
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8084/healthz
```

## Runtime data

- secrets stay in `.env` on the server
- SQLite data persists in the external Docker volume `obecnosc-instance`
- uploaded signatures and generated invoice/report files stay on the server in `static`, `invoices`, and `reports`
- `szablon.docx` and `rejestr.docx` stay on the server and are mounted read-only into the container

## Updating production

After the initial setup, each push to `master` should be enough. The workflow will:

- pull the latest repo on the server
- pull the exact image built for the current commit
- apply database migrations with `flask db upgrade`
- recreate the container with `docker compose -f docker-compose.prod.yml up -d`
- verify the app using `http://127.0.0.1:8084/healthz`